<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/network-config | lastmod: 2026-11-03 | section: Administration / Deployment -->
> 來源：https://code.claude.com/docs/zh-TW/network-config（官方 zh-TW，lastmod 2026-11-03）｜分類：Administration › Deployment｜EN 摘要：Configure Claude Code for enterprise environments with proxy servers, custom Certificate Authorities (CA), and mutual Transport Layer Security (mTLS) authentication.

# 企業網路設定

> 為企業環境設定 Claude Code，包括代理伺服器、自訂憑證授權單位 (CA) 和相互傳輸層安全性 (mTLS) 驗證。

Claude Code 透過環境變數支援各種企業網路和安全設定。這包括透過公司代理伺服器路由流量、信任自訂憑證授權單位 (CA)，以及使用相互傳輸層安全性 (mTLS) 憑證進行驗證以增強安全性。

在啟動 Claude Code 之前，請設定這些環境變數。在您的 shell 中匯出的變數只會在啟動時讀取一次，因此執行中的工作階段不會取得您 shell 環境的後續變更。

> [!NOTE]
>
> 本頁面顯示的所有環境變數也可以在 [`settings.json`](https://code.claude.com/docs/zh-TW/settings) 中設定。

## 代理設定

### 環境變數

Claude Code 遵守標準代理環境變數。在 Claude Desktop 工作階段中，應用程式管理提供者連線時，Claude Code 只會從受管設定和 `~/.claude/settings.json` 讀取這些變數；請參閱 [mTLS 驗證](#mtls-authentication)以了解範圍規則。

```bash theme={null}
# HTTPS 代理（建議）
export HTTPS_PROXY=https://proxy.example.com:8080

# HTTP 代理（如果 HTTPS 不可用）
export HTTP_PROXY=http://proxy.example.com:8080

# 略過特定請求的代理 - 空格分隔格式
export NO_PROXY="localhost 192.168.1.1 example.com .example.com"
# 略過特定請求的代理 - 逗號分隔格式
export NO_PROXY="localhost,192.168.1.1,example.com,.example.com"
# 略過所有請求的代理
export NO_PROXY="*"
```

小寫變體也可以使用，Claude Code 會按照 `https_proxy`、`HTTPS_PROXY`、`http_proxy`、`HTTP_PROXY` 的順序使用第一個已設定的變數。

Claude Code 永遠不會透過代理傳送其 WebSocket 連線到 `localhost`、`::1` 或 `127.0.0.0/8`，因此您不需要在 `NO_PROXY` 中為它們新增迴圈位址項目。

> [!NOTE]
>
> Claude Code 不支援 SOCKS 代理。

### 基本驗證

如果您的代理需要基本驗證，請在代理 URL 中包含認證資訊：

```bash theme={null}
export HTTPS_PROXY=http://username:password@proxy.example.com:8080
```

> [!WARNING]
>
> 避免在指令碼中硬編碼密碼。改用環境變數或安全認證儲存。

> [!TIP]
>
> 對於需要進階驗證（NTLM、Kerberos 等）的代理，請考慮使用支援您驗證方法的 LLM Gateway 服務。

## CA 憑證存放區

根據預設，Claude Code 信任其捆綁的 Mozilla CA 憑證和您作業系統的憑證存放區。讀取作業系統存放區需要具有 `tls.getCACertificates` 的執行時環境：原生安裝程式始終具有它，npm 安裝需要 Node 22.15 或更新版本。在較舊的 Node 版本上，只有捆綁的集合和 `NODE_EXTRA_CA_CERTS` 適用。企業 TLS 檢查代理伺服器在其根憑證安裝在作業系統信任存放區中且執行時可以讀取它時，無需額外設定即可運作。如果此類代理伺服器無法正確處理 gzip 壓縮的請求主體，請設定 [`CLAUDE_CODE_GZIP_REQUEST_BODIES=0`](https://code.claude.com/docs/zh-TW/env-vars) 以關閉 Claude API、遙測和 artifact 發布請求的壓縮。

`CLAUDE_CODE_CERT_STORE` 接受以逗號分隔的來源清單。認可的值為 `bundled`（Claude Code 隨附的 Mozilla CA 集合）和 `system`（作業系統信任存放區）。預設值為 `bundled,system`。

若只信任捆綁的 Mozilla CA 集合：

```bash theme={null}
export CLAUDE_CODE_CERT_STORE=bundled
```

若只信任作業系統憑證存放區：

```bash theme={null}
export CLAUDE_CODE_CERT_STORE=system
```

> [!NOTE]
>
> `CLAUDE_CODE_CERT_STORE` 在 `settings.json` 中沒有專用的架構金鑰。透過 `~/.claude/settings.json` 中的 `env` 區塊或直接在程序環境中設定。

## 自訂 CA 憑證

如果您的企業環境使用自訂 CA，請設定 Claude Code 以直接信任它：

```bash theme={null}
export NODE_EXTRA_CA_CERTS=/path/to/ca-cert.pem
```

## mTLS 驗證

對於需要用戶端憑證驗證的企業環境：

```bash theme={null}
# 用於驗證的用戶端憑證
export CLAUDE_CODE_CLIENT_CERT=/path/to/client-cert.pem

# 用戶端私密金鑰
export CLAUDE_CODE_CLIENT_KEY=/path/to/client-key.pem

# 選用：加密私密金鑰的密碼
export CLAUDE_CODE_CLIENT_KEY_PASSPHRASE="your-passphrase"
```

Claude Code 在啟動時讀取憑證和金鑰檔案，並在每次套用設定時重新讀取它們，例如當您的組織在工作階段中期變更[受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)中的 `env` 區塊時。

若要輪換憑證和金鑰，請替換相同路徑上的檔案。Claude Code 會在執行中的工作階段中選取替換，無需重新啟動。當 API 要求因連線層級錯誤（例如連線重設或 TLS 握手錯誤）而失敗時，它會重新讀取兩個檔案，並使用新的金鑰對重試要求。在 v2.1.232 之前，Claude Code 不會在連線錯誤時重新讀取，因此它會保留已載入的金鑰對，直到下次套用設定或您重新啟動為止。

Claude Code 會根據失敗的要求重新讀取檔案，而不是透過監視檔案變更：

* **時機**：當您替換檔案時，Claude Code 不會執行任何操作。它會在符合條件的失敗後的重試時或下次套用設定時呈現新的金鑰對，以先發生者為準。
* **閘道拒絕**：當您的閘道重設連線或在停止接受舊金鑰對後拒絕 TLS 握手時，Claude Code 會重新讀取。當閘道完成握手並以 HTTP 錯誤回應時，它不會重新讀取。在這種情況下，Claude Code 會在下次套用設定時或重新啟動時載入新的金鑰對。
* **半寫入的輪換**：當 Claude Code 在您的輪換進行中期重新讀取時（例如讀取不相符的憑證和金鑰），它會保留先前的金鑰對，並在下次失敗時重新讀取。
* **OTLP 遙測匯出工具**：Claude Code 會保留[匯出工具](https://code.claude.com/docs/zh-TW/monitoring-usage.md#mtls-authentication)在首次使用時載入的憑證，因此請重新啟動 Claude Code 以便輪換的憑證到達您的遙測收集器。
* **關閉重新載入**：設定 [`CLAUDE_CODE_DISABLE_MTLS_RELOAD_ON_STALE_CONNECTION=1`](https://code.claude.com/docs/zh-TW/env-vars#variables) 以關閉連線錯誤重新讀取。Claude Code 之後只會在下次套用設定或下次啟動時選取輪換的檔案。

若要確認 Claude Code 已選取輪換，請[使用偵錯記錄啟動工作階段](#verify-your-configuration)，並在記錄中尋找 `Stale connection — reloaded rotated mTLS client material`。當 Claude Code 在套用設定時選取輪換時，它不會記錄此行，因此單獨缺少此行並不表示輪換失敗。

在目前金鑰對過期之前替換檔案，以便 Claude Code 不會在下次啟動時載入已過期的金鑰對。

在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，託管環境會管理與 API 的連線，因此當這些變數來自設定檔 `env` 區塊時，Claude Code 會忽略它們：

* `CLAUDE_CODE_CLIENT_CERT`
* `CLAUDE_CODE_CLIENT_KEY`
* `CLAUDE_CODE_CLIENT_KEY_PASSPHRASE`
* `NODE_EXTRA_CA_CERTS`
* `NODE_TLS_REJECT_UNAUTHORIZED`
* `CLAUDE_CODE_OAUTH_SCOPES`

Claude Code 會在工作階段的偵錯記錄中記錄每個被忽略的金鑰。

在由應用程式管理提供者連線的 [Claude Desktop](https://code.claude.com/docs/zh-TW/desktop.md) 工作階段中（例如[第三方提供者](https://code.claude.com/docs/zh-TW/third-party-integrations.md)上的 Code 標籤和 Cowork 工作階段），Claude Code 只會從[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)和 `~/.claude/settings.json` 讀取這些變數（`CLAUDE_CODE_OAUTH_SCOPES` 除外）以及代理伺服器變數 `HTTP_PROXY`、`HTTPS_PROXY` 和 `NO_PROXY`。它會忽略儲存庫自己的設定檔中的這些變數，因此簽出的儲存庫無法重新導向憑證來自應用程式的工作階段的 TLS 或代理伺服器路徑。在 v2.1.217 之前，當應用程式管理連線時，Claude Code 會忽略每個設定檔中的這些變數。

在透過 claude.ai 登入的本機、SSH 或 WSL Code 標籤工作階段中，您可以在任何設定檔中設定這些變數和代理伺服器變數，`CLAUDE_CODE_OAUTH_SCOPES` 除外。Desktop 會在 Code 標籤和 Cowork 工作階段中自行設定 `CLAUDE_CODE_OAUTH_SCOPES`，因此您無法設定它。

當工作階段的啟動環境已設定某個變數時，Claude Code 會[忽略設定檔中的值](https://code.claude.com/docs/zh-TW/settings-reference.md#how-env-values-interact-with-your-shell)，並在[偵錯日誌](https://code.claude.com/docs/zh-TW/debug-your-config.md)中列出該變數的名稱。若要在本機工作階段中使用您自己的代理伺服器或憑證值，請[將其新增至已儲存的本機環境](https://code.claude.com/docs/zh-TW/desktop.md#set-environment-variables-for-local-sessions)。[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)無論您在何處啟動，都遵循上述雲端工作階段規則。

## 驗證您的設定

您通常會從稍後請求時的[連線或憑證錯誤](https://code.claude.com/docs/zh-TW/errors.md#network-and-connection-errors)中發現代理位址錯誤或憑證路徑不正確的問題，因為 Claude Code 在讀取這些設定時不會驗證大多數設定。它在啟動時檢查的唯一設定是代理 URL：當它無法解析該值（例如缺少 `http://` 配置）時，Claude Code 會停止啟動並顯示錯誤，指出要修正的變數。

若要在傳送請求前確認您的設定已載入，請使用偵錯記錄啟動 Claude Code：

```bash theme={null}
claude --debug
```

偵錯輸出會進入 `~/.claude/debug/<session-id>.txt` 而不是終端機，或進入您使用 `--debug-file <path>` 設定的路徑。在日誌中，尋找確認每個檔案已載入的行：

```text theme={null}
CA certs: Appended extra certificates from NODE_EXTRA_CA_CERTS (/etc/ssl/certs/corp-ca.pem)
mTLS: Loaded client certificate from CLAUDE_CODE_CLIENT_CERT
mTLS: Loaded client key from CLAUDE_CODE_CLIENT_KEY
```

如果 Claude Code 無法讀取其中一個檔案，日誌會改為顯示 `Failed to read` 或 `Failed to load` 行及其原因。

您也可以在互動式工作階段中執行 `/status` 並檢查這些列：

* **Proxy**：顯示作用中的代理 URL，並將無法解析的值標記為無效且被忽略。
* **mTLS client cert** 和 **mTLS client key**：僅在檔案載入時出現，因此缺少列表示載入失敗，偵錯日誌中有原因。
* **Additional CA cert(s)**：顯示 `NODE_EXTRA_CA_CERTS` 路徑而不檢查檔案是否已載入，因此請在偵錯日誌中確認此項。

## 將網路設定套用至背景 agent

[背景 agent](https://code.claude.com/docs/zh-TW/agent-view.md) 並不會在派送它們的終端機內執行。每位使用者各有一個監督程序，會在需要時啟動、存續時間比您的 shell 更久，並承載所有 `claude agents`、`--bg` 與 `/background` 工作階段。請參閱[背景工作階段的承載方式](https://code.claude.com/docs/zh-TW/agent-view.md#how-background-sessions-are-hosted)。這會改變本頁的設定傳遞至這些工作階段的方式。

### 在設定中設定網路變數，而非在 shell 中

監督程序是所有終端機共用的單一程序。它會繼承最先啟動它的 shell 的環境。如果您只在 shell 中匯出代理伺服器、CA 路徑或 mTLS 變數，那麼當恰好是該 shell 冷啟動監督程序時，這些變數才會傳遞至背景 agent；若是由其他 shell 啟動，這些變數便不會傳遞過去，且不會有任何提示。

請改為將相同的變數放入 `~/.claude/settings.json` 或[受管設定](https://code.claude.com/docs/zh-TW/settings.md)的 `env` 區塊中。本頁的每個變數都可以在該處設定，而設定是唯一能傳遞至每台機器上每個背景工作階段的設定方式。

### 將企業啟動器設定為設定項目

部分組織要求每個 Claude Code 程序都必須透過企業啟動器啟動，以套用沙箱機制、網路控制或憑證注入。監督程序及其 worker 會從固定路徑啟動 Claude Code，而非在 `PATH` 上查找 `claude`，因此每個背景 agent 都會略過您放在 `PATH` 前段的包裝程式。

請設定 [`processWrapper`](https://code.claude.com/docs/zh-TW/settings-reference#processwrapper) 設定項目，以您的啟動器作為監督程序、其 worker，以及[啟動器涵蓋的範圍](https://code.claude.com/docs/zh-TW/corporate-launcher.md#what-the-launcher-covers)中所列其他背景程序的前綴。兩者皆有設定時，對應的 [`CLAUDE_CODE_PROCESS_WRAPPER`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數優先，且同樣適用相同規則：請透過受管設定或 `~/.claude/settings.json` 提供，而非使用 shell 匯出。[在企業啟動器後方執行 Claude Code](https://code.claude.com/docs/zh-TW/corporate-launcher.md) 說明了啟動器必須遵守的約定、它能與不能觸及的範圍，以及如何推行部署。

> [!NOTE]
>
> 已在執行中的監督程序會保留其啟動時的啟動設定。部署啟動器設定後，請執行 [`claude daemon stop --any`](https://code.claude.com/docs/zh-TW/agent-view#the-supervisor-process)，讓下一次的 `claude agents` 或 `--bg` 啟動一個會遵循該設定的監督程序。

## 串流閒置監視狗

Claude Code 執行四個獨立計時器，當串流模型回應變得安靜時會中止該回應，因此死連線會失敗並重試，而不是掛起。完全沒有收到回應標頭的請求會以下列兩種方式之一結束：

* **在首位元組期限執行的連線上**：第一次嘗試最遲會在該期限結束。若要變更，請設定 `CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS`。有關重試的等待時間，請參閱 [API 無回應](https://code.claude.com/docs/zh-TW/errors.md#no-response-from-api)。
* **在其他連線上**：請求會在 5 到 6 分鐘後、本體閒置逾時觸發時結束，除非您已關閉該逾時。若要更早結束，請降低 `API_TIMEOUT_MS`。在 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段中，您也可以改為[開啟首位元組期限](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#retry-an-unanswered-request-sooner-with-the-first-byte-deadline)，以更早結束第一次嘗試。

| 計時器 | 中止條件 | 執行位置 | 預設逾時 |
| :- | :- | :- | :- |
| 首位元組期限 | Claude Code 傳送請求後沒有回應標頭到達 | 直接 Anthropic API 和 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)，包括透過 HTTPS 代理伺服器，但不包括當 `ANTHROPIC_BASE_URL` 或 `ANTHROPIC_AWS_BASE_URL` 透過 [閘道](https://code.claude.com/docs/zh-TW/gateways.md) 路由時。在 [Claude apps 閘道工作階段](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#retry-an-unanswered-request-sooner-with-the-first-byte-deadline) 中可選擇加入，在 Amazon Bedrock 上使用 `CLAUDE_ENABLE_BYTE_WATCHDOG_BEDROCK=1` 也可選擇加入；不在 Google Cloud 的 Agent Platform 或 Microsoft Foundry 上執行 | 直接 Anthropic API 上 180 秒，Claude Platform on AWS 或 Amazon Bedrock 上 300 秒，加上每 32KB 請求本體一秒 |
| 事件層級監視狗 | 沒有回應事件解析。在位元組層級監視狗執行於 Amazon Bedrock 以外的連線上時，到達的位元組（包括保活 ping）也會重設此監視狗，但在沒有解析事件的情況下僅限一段有限的時間。當位元組至少每 10 秒到達一次時，該時間約為五分鐘。在 Claude apps 閘道每 15 秒一次的 ping 下，該時間約為 7.5 分鐘，因此在預設逾時下，僅有 ping 的串流會在約 12.5 分鐘後結束。 | 每個提供者 | 300 秒 |
| 位元組層級監視狗 | 網路上沒有位元組到達，包括 SSE 保活 ping | 直接 Anthropic API、[Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 和 [閘道](https://code.claude.com/docs/zh-TW/gateways.md) 連線，包括自訂 `ANTHROPIC_BASE_URL`。在 Amazon Bedrock `vnd.amazon.eventstream` 回應上選擇加入，使用 `CLAUDE_ENABLE_BYTE_WATCHDOG_BEDROCK=1`；不在 Google Cloud 的 Agent Platform 或 Microsoft Foundry 上執行 | 直接 Anthropic API 上 180 秒。在 Claude Platform on AWS、Amazon Bedrock、[Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段中，以及透過自訂 `ANTHROPIC_BASE_URL` 時為 300 秒 |
| 本體閒置逾時 | 5 分鐘內沒有位元組到達，包括等待回應標頭的時間 | 提供者不是直接 Anthropic API、Claude Platform on AWS 和設定了 `CLAUDE_ENABLE_BYTE_WATCHDOG_BEDROCK=1` 的 Amazon Bedrock，除非 [`API_FORCE_IDLE_TIMEOUT`](https://code.claude.com/docs/zh-TW/env-vars) 改變該設定 | 5 分鐘 |

如果您設定 `CLAUDE_ENABLE_BYTE_WATCHDOG_BEDROCK=1`，位元組層級監視狗會在 Bedrock 上取代本體閒置逾時，而不是與其並行執行。`CLAUDE_STREAM_IDLE_TIMEOUT_MS` 隨後也會控制 Bedrock 串流在 Claude Code 將連線視為死連線之前可以保持安靜多長時間，在下列列出的限制範圍內。到達的位元組仍不會在 Bedrock 上重設事件層級監視狗。啟用偵錯記錄時，每個 Bedrock 串流隨後會記錄一條以 `wire-heartbeat: _chunkTimes absent` 開頭的偵錯訊息。

使用這些變數設定計時器，每個都在 [環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md) 中詳細說明：

* `CLAUDE_ENABLE_STREAM_WATCHDOG` 和 `CLAUDE_ENABLE_BYTE_WATCHDOG` 在表格列出的連線內，使用 `1` 強制對應的監視狗開啟或使用 `0` 關閉；兩個變數都不會將監視狗擴展到它不涵蓋的連線類型。`CLAUDE_ENABLE_BYTE_WATCHDOG` 設定為 `0` 也會關閉首位元組期限。
* `CLAUDE_STREAM_IDLE_TIMEOUT_MS` 設定兩個監視狗的逾時。Claude Code 將低於 5 分鐘的值提高到 5 分鐘，並將位元組層級監視狗的值上限設為 30 分鐘。
* `CLAUDE_BYTE_STREAM_IDLE_TIMEOUT_MS` 設定位元組層級監視狗的逾時，而不改變事件層級監視狗的逾時，限制在 10 秒到 30 分鐘之間，並優先於 `CLAUDE_STREAM_IDLE_TIMEOUT_MS` 用於該監視狗。
* `CLAUDE_STREAM_FIRST_BYTE_TIMEOUT_MS` 設定首位元組期限。在 Claude apps 閘道工作階段中，設定此變數即可[開啟該期限](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#retry-an-unanswered-request-sooner-with-the-first-byte-deadline)。在期限執行的其他連線上，若您未設定此變數，Claude Code 會使用位元組層級監視狗的逾時，因此 `CLAUDE_STREAM_IDLE_TIMEOUT_MS` 和 `CLAUDE_BYTE_STREAM_IDLE_TIMEOUT_MS` 也會改變期限。有關此值的限制，請參閱 [API 無回應](https://code.claude.com/docs/zh-TW/errors.md#no-response-from-api)。
* `API_TIMEOUT_MS` 限制等待回應標頭的時間，而非回應在標頭之後串流的時間長度。在首位元組期限不執行的情況下，請將 `API_TIMEOUT_MS` 設定為低於 `300000` 的正值，以便在 5 分鐘內重試未獲回應的請求。請將 `API_TIMEOUT_MS` 保持在高於您預期的最長標頭等待時間，以及最長的[非串流請求](https://code.claude.com/docs/zh-TW/errors.md#streaming-response-ended-before-any-complete-data-was-received)時間：需要更長時間的請求在每次重試時都會再次逾時。
* `API_FORCE_IDLE_TIMEOUT` 設定為 `0` 會關閉本體閒置逾時，設定為 `1` 會為每個提供者開啟它。監視狗獨立於它執行，因此要讓串流暫停時間超過其閾值，也要提高或停用它們。

當監視狗中止停滯的串流時，Claude Code 將中止視為中流失敗，您看到的內容取決於回應進行的距離。Claude Code 重試請求或以錯誤結束回合，保留已完成的輸出並顯示 [不完整回應通知](https://code.claude.com/docs/zh-TW/errors.md#the-response-above-may-be-incomplete)，或正常結束回合。[自動重試](https://code.claude.com/docs/zh-TW/errors.md#automatic-retries) 說明每個結果適用的位置。

在 [非互動式工作階段](https://code.claude.com/docs/zh-TW/headless.md) 中，以及任何工作階段中子代理的回應，Claude Code 可能首先提示 Claude 繼續被截斷的回應；[該通知的項目](https://code.claude.com/docs/zh-TW/errors.md#the-response-above-may-be-incomplete) 說明何時執行此操作以及何時您仍然看到通知。

當首位元組期限觸發時，沒有回應已開始，因此沒有部分輸出可保留。有關 Claude Code 如何重新傳送請求以及何時回合改為結束，請參閱 [API 無回應](https://code.claude.com/docs/zh-TW/errors.md#no-response-from-api)。

## 網路存取需求

Claude Code 需要存取下列 URL。在您的代理設定和防火牆規則中將這些 URL 加入允許清單，特別是在容器化或受限網路環境中。當無法連線到 `api.anthropic.com` 或 `platform.claude.com` 時，首次執行設定連線檢查會指向這裡；請參閱[無法連線到 Anthropic 服務](https://code.claude.com/docs/zh-TW/errors.md#unable-to-connect-to-anthropic-services)以了解檢查的訊息和復原步驟。

| URL | 用途 |
| - | - |
| `api.anthropic.com` | Claude API 請求，包括 WebFetch [網域安全檢查](https://code.claude.com/docs/zh-TW/data-usage.md#webfetch-domain-safety-check)、功能旗標擷取和遙測事件記錄 |
| `claude.ai` | claude.ai 帳戶驗證 |
| `claude.com` | claude.ai 帳戶登入會在瀏覽器中開啟 `claude.com` 頁面，該頁面會重新導向到 `claude.ai`；預先核准的 WebFetch 文件查詢也會從 CLI 連線到此主機 |
| `platform.claude.com` | Anthropic Console 帳戶驗證。OAuth 權杖交換、重新整理和撤銷也會連線到此主機以供 claude.ai 帳戶使用，因此 Console 和 claude.ai 登入都需要它 |
| `sso.claude.com` | 使用單一登入（SSO）之組織的瀏覽器登入流程的一部分。如果代理伺服器封鎖此主機，這些登入可能會失敗 |
| `mcp-proxy.anthropic.com` | [來自 claude.ai 的 MCP 連接器](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-servers-from-claude-ai)，包括組織管理員設定的連接器。連接器流量會透過此代理路由；對於 claude.ai 驗證的使用者，連接器預設為啟用。若要停止 Claude Code 擷取它們，請設定 [`ENABLE_CLAUDEAI_MCP_SERVERS=false`](https://code.claude.com/docs/zh-TW/env-vars) 或 [`disableClaudeAiConnectors`](https://code.claude.com/docs/zh-TW/settings-reference#disableclaudeaiconnectors) 設定 |
| `downloads.claude.ai` | 外掛程式可執行檔下載；原生安裝程式、原生自動更新程式和更新版本檢查 |
| `storage.googleapis.com` | 在 `/plugin` 中顯示的外掛程式安裝計數和中繼資料 |
| `storage.googleapis.com` | 2.1.116 之前版本上的原生安裝程式和原生自動更新程式 |
| `registry.npmjs.org` | 外掛程式安裝（擷取 npm 來源外掛程式套件和安裝外掛程式的 Node.js 套件相依性）、`npx` 啟動的 MCP 伺服器，以及 npm 和 bun 安裝 Claude Code 本身的套件登錄 |
| `bridge.claudeusercontent.com` | [Chrome 中的 Claude](https://code.claude.com/docs/zh-TW/chrome.md) 擴充功能 WebSocket 橋接 |
| `*.frame.claudeusercontent.com` | [Artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 內容讀取。當 Claude 開啟 Artifact 時，CLI 會從此主機擷取 Artifact 的檔案，且僅當 Artifact 工具[可用](https://code.claude.com/docs/zh-TW/artifacts.md#availability)於您的帳戶時。若要關閉工具並移除此需求，請設定 [`"enableArtifact": false`](https://code.claude.com/docs/zh-TW/settings-reference#enableartifact) 或 [`CLAUDE_CODE_DISABLE_ARTIFACT=1`](https://code.claude.com/docs/zh-TW/env-vars) |
| `github.com` | 複製 GitHub 託管的[外掛程式市集](https://code.claude.com/docs/zh-TW/plugins/overview.md)和外掛程式，包括官方 Anthropic 市集，透過 HTTPS 或 SSH。若要僅透過 HTTPS 複製 GitHub `owner/repo` 來源，請設定 [`CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`](https://code.claude.com/docs/zh-TW/env-vars) |
| `raw.githubusercontent.com` | [`/release-notes`](https://code.claude.com/docs/zh-TW/commands) 的變更日誌摘要。在互動式工作階段中，Claude Code 也會在啟動時在背景擷取它，當其快取的變更日誌尚未涵蓋執行中的版本時，例如更新後的首次啟動；非互動式和雲端工作階段永遠不會擷取它 |
| `*-review.googlesource.com` | 在 `googlesource.com` 簽出上進行 Gerrit 變更查詢。當 Claude Desktop Code 索引標籤工作階段在[受信任](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)的簽出上啟動或繼續時，其 `origin` 是 `googlesource.com` 主機，Claude Code 會匿名詢問該主機的 `-review` 伺服器，以取得與 HEAD 的 `Change-Id` 相符的開啟變更，每次啟動或繼續一次。其他工作階段類型會略過查詢，且不會連線到其他 Gerrit 主機。選用：使用 [`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars) 停用 |
| `http-intake.logs.us5.datadoghq.com` | 操作遙測事件，僅在 CLI 直接使用 Anthropic API 時傳送，絕不會用於 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry。選用：使用 [`DISABLE_TELEMETRY`](https://code.claude.com/docs/zh-TW/data-usage#telemetry-services) 或 `DO_NOT_TRACK` 停用 |
| `browser-intake-us5-datadoghq.com` | 操作錯誤報告，在 CLI 直接使用 Anthropic API 且伺服器端推出閘道啟用它們時傳送。選用：使用 `DISABLE_ERROR_REPORTING` 或 `DISABLE_TELEMETRY` 停用；請參閱[遙測服務](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services) |
| `formulae.brew.sh` | Homebrew 安裝上的更新版本檢查。其他安裝方法不會連線到此主機 |
| `code.claude.com` | 內建 claude-code-guide 代理程式和預先核准的 WebFetch 請求進行的 Claude Code 文件查詢。阻止此主機只會影響文件查詢 |

如果您透過 npm 安裝 Claude Code 或管理自己的二進位分佈，終端使用者不需要原生安裝程式和 `downloads.claude.ai` 的自動更新程式用途，但 npm 和 bun 安裝需要其套件登錄 `registry.npmjs.org`，除非您的組織鏡像它。表中的其他用途無論安裝方法為何都適用。

兩個 Datadog 進入主機僅攜帶選用的操作遙測，設定 [`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars) 會停用兩者。第三方提供者上的工作階段永遠不會傳送到這些主機，即使平台設定 [`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`](https://code.claude.com/docs/zh-TW/env-vars) 且遙測指標預設為開啟。請參閱[遙測服務](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services)以了解 Claude Code 傳送的所有內容以及如何在完成允許清單之前停用它。

### 雲端提供者和 LLM 閘道路由

使用 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)、[Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 或已登入的 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)工作階段時，模型流量和驗證會連線到您的提供者或閘道，而不是 `api.anthropic.com`、`claude.ai` 或 `platform.claude.com`。WebFetch 工具仍會呼叫 `api.anthropic.com` 進行其[網域安全檢查](https://code.claude.com/docs/zh-TW/data-usage.md#webfetch-domain-safety-check)，除非您在[設定](https://code.claude.com/docs/zh-TW/settings.md)中設定 `skipWebFetchPreflight: true`。

如果您的開發人員在透過 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/llm-gateway-connect#set-the-base-url-and-credential) 設定的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)後面使用[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)，請保持 `api.anthropic.com` 可透過您的代理伺服器連線。當 Claude Code 傳送快速模式可用性檢查時，該檢查會透過任何已設定的 HTTP 代理伺服器連線到該主機，絕不會連線到閘道。若要了解何時不會傳送檢查，以及在各種情況下恢復快速模式的變數，請參閱[在代理伺服器和 LLM 閘道後面使用快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md#use-fast-mode-behind-proxies-and-llm-gateways)。

### 組織 IP 允許清單和代理出口

如果您的組織已[啟用 IP 允許清單](https://support.claude.com/en/articles/13200993-restrict-access-to-claude-with-ip-allowlisting)用於 Claude，請透過與 `claude.ai` 和 `api.anthropic.com` 相同的代理出口路由 `bridge.claudeusercontent.com`，例如將其放在相同的 Zscaler 應用程式區段或 Netskope 轉向原則中。如果您無法以這種方式路由它，請將您的代理用於該主機的出口位址新增到您的組織 IP 允許清單，但僅當該位址專用於您的組織時：共用代理出口範圍也允許代理廠商的其他客戶。

Anthropic 使用它們到達的位址檢查與 `bridge.claudeusercontent.com` 的連線，針對您的組織 IP 允許清單。如果您的代理透過不在該允許清單上的位址傳送該主機的流量，Claude Code 無法連線到 [Chrome 中的 Claude](https://code.claude.com/docs/zh-TW/chrome.md) 擴充功能，即使 Claude Code 的其餘部分有效。

### GitHub 允許清單和防火牆

Anthropic 託管環境中的[網路上的 Claude Code](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md) 和[程式碼審查](https://code.claude.com/docs/zh-TW/code-review.md)從 Anthropic 管理的基礎設施連線到您的儲存庫；[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中的工作階段從您的網路內部連線，除非執行器選擇加入 [Anthropic git 代理](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#use-the-anthropic-git-proxy)，該代理從 Anthropic 的一側擷取。

如果您的 GitHub Enterprise Cloud 組織按 IP 位址限制存取，請啟用[已安裝 GitHub Apps 的 IP 允許清單繼承](https://docs.github.com/en/enterprise-cloud@latest/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/managing-allowed-ip-addresses-for-your-organization#allowing-access-by-github-apps)，並且也[新增允許清單項目](https://docs.github.com/en/enterprise-cloud@latest/organizations/keeping-your-organization-secure/managing-security-settings-for-your-organization/managing-allowed-ip-addresses-for-your-organization#adding-an-allowed-ip-address)用於 Anthropic 的[出站 IP 位址](https://platform.claude.com/docs/en/api/ip-addresses#outbound-ip-addresses)。繼承僅涵蓋 Claude GitHub App 作為安裝進行的請求，不涵蓋它代表您的使用者進行的請求。對於其他防火牆，請參閱 [Anthropic API IP 位址](https://platform.claude.com/docs/en/api/ip-addresses)。

對於防火牆後面的自託管 [GitHub Enterprise Server](https://code.claude.com/docs/zh-TW/github-enterprise-server.md) 執行個體，允許清單 Anthropic 的[出站 IP 位址](https://platform.claude.com/docs/en/api/ip-addresses#outbound-ip-addresses)，以便 Anthropic 基礎設施可以連線到您的 GHES 主機以複製儲存庫和發佈審查評論。[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#configure-git)中的工作階段改為從您的網路內部連線到您的 GHES 主機，因此該曝露僅適用於 Anthropic 託管工作階段、託管前工作階段流程（例如儲存庫選擇器）以及選擇加入 [Anthropic git 代理](https://code.claude.com/docs/zh-TW/self-hosted-environments-deploy.md#use-the-anthropic-git-proxy)的自託管執行器，該代理從 Anthropic 的一側擷取。[SCM 連接器](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#scm-connector-flags)無法使用，因此託管前工作階段流程無法連線到僅在您的網路內部可路由的 GHES 主機。

### 桌面和 claude.ai

前面的表格涵蓋獨立 CLI。Claude Desktop 應用程式和瀏覽器中的 claude.ai 從其他 Anthropic CDN 主機載入其應用程式程式碼和使用者內容，包括 `assets-proxy.anthropic.com` 和其他在這些應用程式中提供 [Artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 的 `*.claudeusercontent.com` 來源。允許 `claude.ai` 同時阻止這些主機會產生空白頁面而不是錯誤。請參閱 Desktop 頁面上的[網路存取需求](https://code.claude.com/docs/zh-TW/desktop.md#network-access-requirements)。

Claude Desktop 和 claude.ai 也會將對話中的部分工具結果呈現為互動式小工具，例如某些連接器提供的 [MCP Apps](https://claude.com/docs/connectors/building/mcp-apps/getting-started)。這些小工具從 `claudemcpcontent.com` 的產生子網域載入，因此請允許 `*.claudemcpcontent.com` 並保留萬用字元。如果您阻止它，應用程式的其餘部分仍可正常運作，但這些小工具不會載入。

#### Artifact 字型和程式庫的第三方主機

從 [Google Fonts](https://code.claude.com/docs/zh-TW/artifacts.md#improve-the-visual-design) 載入字型的 [Artifact](https://code.claude.com/docs/zh-TW/artifacts.md) 也會要求 `fonts.googleapis.com` 和 `fonts.gstatic.com`。兩個主機都是選用的。如果您阻止它們，Artifact 會以備用字型呈現。使用快速拒絕而不是無聲丟棄進行阻止，以便字型要求立即失敗，而不是延遲頁面的首次呈現。

Artifact 也可以從 `cdnjs.cloudflare.com`、`cdn.jsdelivr.net`、`cdn.tailwindcss.com`、`code.jquery.com` 和 `unpkg.com` 載入 JavaScript 程式庫（例如 React 或圖表套件），而不是從任何其他外部主機。如果您阻止這些主機，Artifact 中依賴程式庫的部分將無法運作，與阻止的字型不同，阻止的程式庫沒有備用方案。此處也使用快速拒絕進行阻止，以便阻止的程式庫要求立即失敗，而不是掛起直到逾時。

## 其他資源

* [設定檔和優先順序](https://code.claude.com/docs/zh-TW/settings.md)
* [環境變數參考](https://code.claude.com/docs/zh-TW/env-vars.md)
* [疑難排解指南](https://code.claude.com/docs/zh-TW/troubleshooting.md)

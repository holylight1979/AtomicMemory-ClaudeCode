<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/llm-gateway-protocol | lastmod: 2026-11-03 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/llm-gateway-protocol（官方 zh-TW，lastmod 2026-11-03）｜分類：Administration › Gateways｜EN 摘要：Keep an LLM gateway compatible with Claude Code: the endpoints it calls, the headers and body fields to forward, and what breaks when they're stripped.

# Claude Code 閘道相容性指南

> 保持 LLM 閘道與 Claude Code 相容：它呼叫的端點、必須轉發的標頭和本體欄位，以及移除它們時會中斷的功能。

本頁面記錄 Claude Code 傳送至閘道的請求，包括它呼叫的端點、閘道必須轉發的標頭和本體欄位，以及當閘道未轉發時停止運作的功能。本文件是為配置閘道產品以與 Claude Code 搭配運作的操作人員撰寫的。

[Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 是 Anthropic 的自託管閘道，在 `GET /protocol` 提供自己的端點參考，涵蓋該閘道的登入、推論、受管設定、模型探索和遙測端點。這是與本指南分開的文件。

> [!NOTE]
>
> * 若要為您的組織推出現有或第三方閘道，請參閱[推出 LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway-rollout.md)
> * 如果您是使用獲得的認證向閘道驗證 Claude Code 的個別開發人員，請參閱[將 Claude Code 連線至 LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md)

本頁面涵蓋：

* [API 格式](#api-formats)和每種格式要提供的端點
* [依連線方法的用戶端行為](#how-the-connection-method-changes-client-behavior)：模型 ID、`anthropic-beta` 值、請求欄位和預設值在格式和 Claude apps gateway 登入之間的差異
* [請求標頭](#request-headers)：哪些必須到達上游，以及您的閘道可以使用哪些
* [回應標頭](#response-headers)：要傳回什麼以便停滯偵測、重試和使用量限制顯示能夠運作
* [系統提示屬性區塊](#system-prompt-attribution-block)及其與提示快取的互動方式
* [功能傳遞](#feature-pass-through)：移除標頭或本體欄位時會中斷的功能
* [模型探索](#model-discovery)

本頁面使用兩個術語來說明您的閘道對每個標頭和本體欄位的處理方式：

* **轉發不變**：將其逐位元組傳遞至上游
* **使用**：閘道可能會讀取它以進行路由、屬性或追蹤，不需要轉發它

任何未標記為轉發不變的內容都可供您使用或忽略。

## API 格式

閘道必須向 Claude Code 用戶端公開以下至少一種 API 格式。用戶端會選擇一種格式，並使用下表「選擇者」欄中的變數將 Claude Code 指向您的閘道。

Google Cloud 的 Agent Platform 是 Google Cloud 的 Claude 端點，前身為 Vertex AI；其變數名稱保留 `VERTEX` 拼寫。

| 格式 | 選擇者 | 端點 | 轉發不變 |
| :- | :- | :- | :- |
| Anthropic Messages | `ANTHROPIC_BASE_URL` | `/v1/messages`、`/v1/messages/count_tokens`（選用） | `anthropic-beta` 和 `anthropic-version` 請求標頭 |
| Amazon Bedrock InvokeModel | `ANTHROPIC_BEDROCK_BASE_URL` 搭配 `CLAUDE_CODE_USE_BEDROCK=1` | `/model/{model}/invoke`、`/model/{model}/invoke-with-response-stream`、`/model/{model}/count-tokens`（選用） | `anthropic_beta` 和 `anthropic_version` 請求本體欄位 |
| Google Cloud 的 Agent Platform rawPredict | `ANTHROPIC_VERTEX_BASE_URL` 搭配 `CLAUDE_CODE_USE_VERTEX=1` | `:rawPredict`、`:streamRawPredict`、`count-tokens:rawPredict`（選用） | `anthropic-beta` 和 `anthropic-version` 請求標頭，以及 `anthropic_version` 請求本體欄位 |

### Foundry 和 AWS 上的 Claude Platform

Microsoft Foundry 和 [AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 實作 Anthropic Messages 格式。Claude Code 透過自己的變數 `ANTHROPIC_FOUNDRY_BASE_URL` 和 `ANTHROPIC_AWS_BASE_URL` 路由到它們，但閘道在任一前面實作上述 Anthropic Messages 列。閘道在 AWS 上的 Claude Platform 前面也必須轉發 `anthropic-workspace-id` 標頭，[該平台在每個請求上都需要](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)。

### 選用端點和啟動流量

權杖計數端點是唯一的選用端點：當它們不存在時，Claude Code 會回退到基於字元的內容使用估計。

根據路徑而非完整 URL 進行比對：

* 推論請求發佈到 `/v1/messages?beta=true`
* Google Cloud 的 Agent Platform 方法尾碼附加到發佈者模型路徑，如 `/projects/{project}/locations/{location}/publishers/anthropic/models/{model}:streamRawPredict`

閘道也會看到最佳努力啟動流量，可以拒絕而不會破壞任何東西。Anthropic Messages 格式閘道會收到 `HEAD /api/hello` 連線預熱探測，當設定了 HTTP 代理或用戶端憑證時，Claude Code 會跳過此探測。Amazon Bedrock 格式閘道會收到 `GET /inference-profiles?type=SYSTEM_DEFINED` 請求，以及當設定的模型是推論設定檔時，`GET /inference-profiles/{profile}` 查詢。

透過閘道的工作階段不符合 HIPAA 設定的資格。[檢查開發人員如何登入和連線](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect)列出了哪些登入和連線方式符合資格。請參閱[閘道後面的 HIPAA 設定](https://code.claude.com/docs/zh-TW/llm-gateway-rollout.md#the-hipaa-configuration-behind-a-gateway)。

[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)可用性檢查永遠不會出現在閘道日誌中：它直接呼叫 `api.anthropic.com` 而不是遵循 `ANTHROPIC_BASE_URL`，因此在阻止直接出站到 `api.anthropic.com` 的網路上，快速模式可能會報告連線錯誤，而透過閘道的推論會繼續運作。[WebFetch 網域安全檢查](https://code.claude.com/docs/zh-TW/data-usage.md#webfetch-domain-safety-check)也直接呼叫 `api.anthropic.com`。[在代理和 LLM 閘道後面使用快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md#use-fast-mode-behind-proxies-and-llm-gateways)涵蓋恢復它的變數。

### 串流

Claude Code 會在每個串流推論回應到達時逐一事件讀取，因此您的閘道轉送串流的方式會影響使用者看到的內容：

* 如果您的閘道在回應完成之前緩衝該回應，Claude Code 會停滯。
* Claude Code 預期依序收到每個回應的完整事件序列，直到最終的 `message_delta` 和 `message_stop` 事件。如果本體在內容區塊已啟動之後、但在該最終 `message_delta` 之前乾淨地結束，Claude Code 會將該回應視為連線中斷。[上述回應可能不完整](https://code.claude.com/docs/zh-TW/errors.md#the-response-above-may-be-incomplete)描述使用者此時看到的內容，[自動重試](https://code.claude.com/docs/zh-TW/errors.md#automatic-retries)則說明 Claude Code 何時改為重新發出請求。
* 當 Amazon Bedrock guardrail 封鎖回覆時，Bedrock 發送的事件可能會參考其 `content_block_stop` 已經到達的內容區塊，而 Claude Code 依賴於按原樣收到這些事件。[AWS Guardrails](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#aws-guardrails) 描述該回覆如何結束。
* 一旦超過其[串流閒置逾時](https://code.claude.com/docs/zh-TW/network-config.md#streaming-idle-watchdogs)都沒有任何位元組到達，Claude Code 就會中止串流回應。在長時間的思考暫停期間，上游的 SSE `ping` 事件可能是串流上唯一的位元組，因此剝離或緩衝這些事件的閘道可能會在回應進行到一半時觸發該逾時。從不發送 ping 的上游（例如 Amazon Bedrock 的二進位事件串流）進行轉譯的閘道也有相同的間隙，除非它發出自己的 `ping` 事件。
* 在 [Amazon Bedrock InvokeModel 格式](#api-formats)上，Claude Code 會將 `/model/{model}/invoke-with-response-stream` 回應讀取為 Bedrock 傳回的二進位 `application/vnd.amazon.eventstream` 本體，一旦閘道將其轉換為伺服器發送事件或改寫該 `Content-Type` 標頭，就無法解析它。[閘道或代理伺服器後面的串流錯誤](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#streaming-errors-behind-a-gateway-or-proxy)描述使用者此時看到的內容。

### 與上游的格式不匹配

用戶端使用的格式決定了您的閘道接收的內容。常見的失敗模式是用戶端發送到您的閘道的格式與其後面的上游提供者接受的格式不匹配。

* 當用戶端使用 Amazon Bedrock 或 Google Cloud 的 Agent Platform 格式時，Claude Code 只發送那些提供者接受的完整功能集的子集
* 當用戶端使用 Anthropic Messages 格式時，Claude Code 發送完整集，即使您的閘道轉發到 Amazon Bedrock 或 Google Cloud 的 Agent Platform 上游

橋接該差異是您的閘道的工作。[功能傳遞](#feature-pass-through)描述當它不這樣做時會破壞什麼。

如果您的上游是 Amazon Bedrock 或 Google Cloud 的 Agent Platform，您可以透過改為公開該提供者的格式來避免橋接。[透過閘道路由到雲端提供者](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#route-to-a-cloud-provider-through-a-gateway)顯示該格式的用戶端設定。

## 連線方法如何改變用戶端行為

開發人員連線到您的閘道的方式決定了 Claude Code 傳送的模型 ID、`anthropic-beta` 值和請求欄位，以及它套用的預設值。您的閘道會看到以下三種用戶端行為之一：

* **Amazon Bedrock 或 Agent Platform 格式**：開發人員設定 `CLAUDE_CODE_USE_BEDROCK=1` 搭配 `ANTHROPIC_BEDROCK_BASE_URL`，或 `CLAUDE_CODE_USE_VERTEX=1` 搭配 `ANTHROPIC_VERTEX_BASE_URL`，指向您的閘道。Claude Code 使用該提供者的模型 ID、請求欄位和預設值。
* **Anthropic Messages 格式**：開發人員將 `ANTHROPIC_BASE_URL` 設定為您的閘道。Claude Code 將閘道視為 Claude API，無法判斷您轉發到哪個上游。
* **Claude apps 閘道登入**：開發人員登入 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)。該閘道使用 Anthropic Messages 格式，但可以路由到任何上游，因此 Claude Code 只傳送 Amazon Bedrock 和 Agent Platform 也接受的 `anthropic-beta` 值和模型功能假設。

### 按連線方法的請求和預設值

下表比較三種連線方法，每行一個行為。它省略了 Microsoft Foundry 和 Claude Platform on AWS，它們也使用 Anthropic Messages 格式，但 Claude Code 透過自己的變數到達它們。如需這些，請參閱 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 和 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 頁面。

| 行為 | Amazon Bedrock 或 Agent Platform 格式 | Anthropic Messages 格式 | Claude apps 閘道登入 |
| :- | :- | :- | :- |
| 預設情況下請求中的模型 ID | 提供者的形式，例如 Amazon Bedrock 上的 `us.anthropic.claude-opus-4-8` | Anthropic ID，例如 `claude-opus-4-8` | Anthropic ID |
| 傳送的 `anthropic-beta` 值 | Amazon Bedrock 和 Agent Platform 接受的子集 | [功能傳遞](#feature-pass-through)下描述的完整集合，除非開發人員設定 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`](#disable-pre-release-capabilities) | Amazon Bedrock 和 Agent Platform 接受的子集 |
| Claude Code 無法識別的模型 ID（例如閘道別名）的請求欄位 | 使用固定預算進行思考而非自適應推理，且沒有努力或內容管理欄位。Claude Code 仍會傳送[對話中途的系統訊息](#feature-pass-through) | 目前 Claude 模型在 Claude API 上接受的所有內容，包括自適應推理、努力和內容管理，Amazon Bedrock 或 Agent Platform 上游可能會拒絕 | 與 Amazon Bedrock 或 Agent Platform 格式相同 |
| 開發人員選擇加入時的一小時 [提示快取 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself) | 透過 `cache_control` 中的 `ttl` 欄位請求，沒有測試版值 | 透過 `ttl` 欄位加上 `anthropic-beta` 中的 `extended-cache-ttl` 值請求，您必須轉發 | 透過 `ttl` 欄位請求，沒有測試版值。請參閱[一小時提示快取](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#one-hour-prompt-cache) |
| [背景工作](https://code.claude.com/docs/zh-TW/costs.md#background-token-usage) 的模型，除非 `ANTHROPIC_DEFAULT_HAIKU_MODEL` 固定一個 | 預設 Sonnet 模型，或選擇主模型後的主模型，如 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#4-pin-model-versions) 和 [Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#5-pin-model-versions) 頁面所述 | 主模型，或當 `ANTHROPIC_API_KEY` 或 `apiKeyHelper` 提供 Anthropic Console 金鑰且 `ANTHROPIC_AUTH_TOKEN` 未設定時的預設 Haiku 模型 | 主模型 |

如需每個連線支援的功能以及它預設傳送給 Anthropic 的遙測，請參閱 [功能可用性](https://code.claude.com/docs/zh-TW/feature-availability.md#availability-by-model-provider) 和 [按 API 提供者的預設行為](https://code.claude.com/docs/zh-TW/data-usage.md#default-behaviors-by-api-provider)。

### 無法識別的模型 ID 的設定

兩個用戶端設定會改變 Claude Code 對無法識別的模型 ID 的假設，無論開發人員使用哪種連線方法：

* **內容視窗**：Claude Code 假設 200K，或當 ID 帶有 `[1m]` 時為 1M。若要宣告實際視窗，請參閱 [更正閘道或自訂模型 ID 的視窗](https://code.claude.com/docs/zh-TW/model-config.md#correct-the-window-for-a-gateway-or-custom-model-id)
* **功能**：若要給閘道別名提供其背後模型的功能，請在您分發的設定中使用 [`modelOverrides`](https://code.claude.com/docs/zh-TW/errors#unrecognized-model-id-on-a-request) 項目將該模型的 Anthropic ID 對應到您的別名。如需 `ANTHROPIC_DEFAULT_*_MODEL_SUPPORTED_CAPABILITIES` 變數適用的位置，請參閱 [功能傳遞](#feature-pass-through)

## 請求標頭

Claude Code 在 API 請求上包含這些標頭。標頭名稱在線路上不區分大小寫。轉發 `anthropic-version` 和 `anthropic-beta` 不變，加上當上游是 [AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 時的 `anthropic-workspace-id`；其餘的 gateway 可以使用以進行路由、歸屬和追蹤，不需要轉發。

| 標頭 | 描述 |
| :- | :- |
| `Authorization`、`x-api-key` | 開發人員的 gateway 認證，根據他們設定的[認證變數](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#set-the-credential-variable)在一個或兩個標頭中 |
| `anthropic-version` | API 版本，目前為 `2023-06-01`。Amazon Bedrock 和 Google Cloud 的 Agent Platform 格式請求也攜帶 `anthropic_version` 請求體欄位，其值是提供者方言字串，而不是此標頭的值 |
| `anthropic-beta` | 請求的逗號分隔功能值。逐字轉發標頭；不要將個別值列入允許清單，因為該集合隨 Claude Code 版本而變化。當開發人員使用 claude.ai 登入進行驗證時（當設定 `ANTHROPIC_BASE_URL` 而沒有 gateway 認證變數時可能），此標頭也會攜帶上游需要的 OAuth 功能，移除它會導致這些請求失敗並出現 `401` |
| `x-claude-code-session-id` | 目前 Claude Code 工作階段的唯一識別碼。使用它來聚合來自一個工作階段的所有請求，而無需解析請求體 |
| `x-claude-code-agent-id` | 發出請求的[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)的識別碼，僅在來自 Claude Code 在工作階段內生成的代理的請求上存在。將其與工作階段 ID 一起使用以將成本歸屬於平行代理 |
| `x-claude-code-parent-agent-id` | 生成請求代理的代理的識別碼，僅對嵌套代理存在 |

子代理 ID 在每次生成時都會新生成。隊友代理（[代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)的命名成員）在重新連接時重複使用穩定的基於名稱的 ID。在兩種情況下，ID 都識別一個代理，而不是一個人或設備，因此不要將代理 ID 標頭視為使用者識別碼。

如果您的開發人員設定了 `ANTHROPIC_CUSTOM_HEADERS`，這些標頭也會出現在請求上。

### Gateway 提示標頭

Claude Code 也可以傳送路由提示：gateway 或路由器可以用來排程、快取或歸屬請求的每個請求事實。需要 Claude Code v2.1.273 或更新版本。

請求是否攜帶它們取決於 Claude Code 將其傳送到何處：

* 直接連接到 Anthropic API：預設傳送
* 自訂基礎 URL：預設關閉，因為拒絕未知標頭的代理會導致請求失敗。若要接收它們，請為您的開發人員設定 [`CLAUDE_CODE_GATEWAY_HINT_HEADERS=1`](https://code.claude.com/docs/zh-TW/env-vars)，例如在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)的 `env` 區塊中
* 任何其他後端，包括 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 和 AWS 上的 Claude Platform：僅在設定 `CLAUDE_CODE_GATEWAY_HINT_HEADERS=1` 時傳送

將 `CLAUDE_CODE_GATEWAY_HINT_HEADERS` 設定為 `0` 會停止每個連接上的標頭。

標頭只攜帶下面列出的內容：固定詞彙、工具名稱、持續時間和隨機提示識別碼，永遠不會是提示文字或檔案內容。每個值都是可列印的 ASCII。

| 標頭 | 描述 |
| :- | :- |
| `x-claude-code-request-class` | 這是什麼類型的請求：`main` 用於主對話的一個回合，`subagent` 用於[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)的一個回合，`workflow` 用於在工作流程內執行的代理，`compaction` 用於壓縮對話的摘要請求，或 `auxiliary` 用於側面請求，例如工作階段標題、分類器和摘要。在每個請求上傳送 |
| `x-claude-code-agent-type` | 發出請求的子代理類型：內建代理類型名稱，例如 `Explore`、`Plan` 或 `general-purpose`，或 `custom` 用於使用者定義的代理，`teammate` 用於在主導者程序中執行的[代理團隊](https://code.claude.com/docs/zh-TW/agent-teams.md)成員，或 `fork` 用於[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)。僅在子代理自己的回合上存在；子代理的壓縮或側面請求保留代理 ID，但不攜帶類型。使用者選擇的代理名稱永遠不會被傳送 |
| `x-claude-code-compaction` | 在[壓縮](https://code.claude.com/docs/zh-TW/prompt-caching.md#compacting-the-conversation)期間摘要對話的請求上存在。該值說明觸發了什麼：`auto` 當上下文視窗接近容量時，`manual` 用於 `/compact`，或 `reactive` 當 API 拒絕請求太長時。對於互動式終端機工作階段中的[閒置壓縮](https://code.claude.com/docs/zh-TW/settings-reference.md#idlecompaction)，該值也是 `auto`。在所有其他請求上不存在，包括在壓縮之前於背景撰寫摘要的請求 |
| `x-claude-code-context-compacted` | 在壓縮後的第一個主對話請求上存在一次，具有與 `x-claude-code-compaction` 相同的值。此請求之前的對話前綴不再使用，因此可以刪除以其為鍵的快取 |
| `x-claude-code-prev-tool-durations` | 此請求攜帶其結果的工具呼叫的測量執行時間，格式為 `<name>=<ms>;<name>=<ms>`，例如 `Bash=742;Read=9`。在同一對話的下一個請求之後傳送，來自主工作階段或子代理的一批工具呼叫 |
| `x-claude-code-prompt-id` | 隨機 UUID，識別請求所服務的使用者提示。服務一個提示的請求共享該值，包括該提示啟動的子代理的回合。未歸屬於提示的請求會省略它。使用它按提示對工作階段的請求進行分組。需要 Claude Code v2.1.283 或更新版本 |

在解析 `x-claude-code-prev-tool-durations` 之前，請檢查 Claude Code 如何建立該值以及它遺漏了什麼：

* 項目：每個執行的工具呼叫一個，按其結果被收集的順序，以整毫秒為單位
* 上限：Claude Code 最多傳送 32 個項目和 4 KB，保留第一個項目
* 編碼：工具名稱是百分比編碼的，涵蓋 `%`、`;`、`=`、逗號、空格和任何超出可列印 ASCII 的字元
* 解析：在 `;` 上分割，然後在 `=` 上分割，並解碼每個名稱
* 缺失：壓縮呼叫、側面請求和新提示的第一個請求永遠不會攜帶它。不要將缺失的標頭讀作執行無工具的回合
* 時間：每個時間都排除了權限提示和 hooks，平行工具呼叫各自報告自己的時間，因此項目不會加起來等於請求之間的間隙

### 作為開放清單轉發

將標頭和請求體欄位視為開放清單，而不是封閉清單。Claude Code 在版本中獲得功能，它們作為新的 `anthropic-beta` 值、新的請求體欄位以及偶爾新的 `anthropic-*` 或 `x-claude-code-*` 標頭到達。

轉發到 Anthropic 格式上游時，傳遞 `anthropic-*` 請求標頭和請求體欄位不變，而不是將您今天看到的列入允許清單。固定到觀察清單的 gateway 會移除下一個功能的標頭或欄位，並在引入它的版本上破壞它。

例外是非 Anthropic 上游（如 Amazon Bedrock 或 Google Cloud 的 Agent Platform），其中橋接架構差異是 gateway 的工作；請參閱[功能傳遞](#feature-pass-through)。

## 回應標頭

Claude Code 讀取這些回應標頭以偵測停滯的串流、決定是否以及何時重試，以及顯示使用量限制。該表列出每個標頭應返回的內容。同時未修改地轉發錯誤回應本體，以便 Claude Code 的[能力拒絕復原](#automatic-retry-and-error-forwarding)可以符合上游的錯誤措辭。

| 標頭 | 應返回的內容及原因 |
| :- | :- |
| `content-type` | 在串流的 Anthropic Messages 格式回應上返回 `text/event-stream`，在 Amazon Bedrock 格式回應上返回 `application/vnd.amazon.eventstream`（未修改），其中[不同的類型會導致請求失敗](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#streaming-errors-behind-a-gateway-or-proxy) |
| `retry-after` | 返回整數秒數而非 HTTP 日期。Claude Code 在下一次[自動重試](https://code.claude.com/docs/zh-TW/errors.md#automatic-retries)之前至少等待該時間長度，在 [`CLAUDE_CODE_RETRY_WATCHDOG`](https://code.claude.com/docs/zh-TW/env-vars) 工作階段外，超過 60 的值會停止重試並立即顯示錯誤 |
| `x-should-retry` | 未修改地傳遞上游的值。Claude Code 在決定是否重試失敗的請求時將此標頭讀取為一個輸入：`true` 標記回應為可重試，`false` 標記為不可重試。如需重試計數、退避和 Claude Code 重試的失敗，請參閱[自動重試](https://code.claude.com/docs/zh-TW/errors.md#automatic-retries) |
| `anthropic-ratelimit-unified-*` | 在每個回應上未修改地轉發上游的值。Claude Code 在成功回應上讀取它們以向使用 claude.ai 登入的開發人員顯示針對計畫限制的使用量，在 `429` 上讀取以區分計畫限制或支出上限與暫時性節流；請參閱[使用量限制](https://code.claude.com/docs/zh-TW/errors.md#usage-limits) |

## 系統提示歸屬區塊

Claude Code 在系統提示前面加上一個簡短的歸屬區塊，其中包含用戶端版本和從對話衍生的指紋。`api.anthropic.com` 端點在處理前移除該區塊，因此它不會影響第一方提示快取；任何其他上游都會將其作為提示的一部分接收。

該移除是位置性的，因此只有在 gateway 轉發 `system` 陣列保持不變時才有效。若要在不遺失其他系統內容的情況下將區塊排除在提示之外：

* 完全按照接收的方式轉發 `system` 陣列，將區塊保持在最前面：在前面加上另一個系統區塊、重新排序陣列或將其轉換為單一字串會破壞移除，區塊隨後會到達模型和提示快取鍵。
* 將區塊保持在自己的陣列項目中：端點將以歸屬標頭開頭的合併區塊視為完整的歸屬並刪除合併到其中的所有內容，包括系統提示的其餘部分。
* 如果您的 gateway 必須重新塑造系統內容，請設定 [`CLAUDE_CODE_ATTRIBUTION_HEADER=0`](https://code.claude.com/docs/zh-TW/env-vars) 以便 Claude Code 省略該區塊。Anthropic 和雲提供者的 Claude 端點讀取該區塊以進行歸屬，因此要省略它，請在用戶端而不是在 gateway 中移除或移動它。

該變數存在是為了 gateway 和第三方快取相容性，而不是作為隱私控制：在直接連線上，完整請求無論如何都已經進入 Anthropic API。當以下兩項都成立時，Claude Code 會在 [auto mode](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) 分類器請求上保留該區塊，即使您將變數設定為 `0`：

* 請求進入 `api.anthropic.com`，`ANTHROPIC_BASE_URL` 未設定或命名該主機，且未選擇第三方提供者。
* 作用中的認證不是 [Anthropic 設定檔或聯盟認證](https://code.claude.com/docs/zh-TW/authentication.md#anthropic-profiles-and-federation-credentials)。

分類器請求會跳過 Claude Code 系統提示的其餘部分，因此在這些請求上，該區塊是請求體中唯一識別它們為 Claude Code 流量的標記。當任一條件失敗時，通過 LLM gateway、在第三方提供者上，或使用作用中的設定檔或聯盟認證，設定 `0` 也會從分類器請求中移除該區塊。在 v2.1.229 之前，此例外不存在：設定 `0` 會從這些分類器請求中移除該區塊，當 API 拒絕未識別的請求時，auto mode 在它發送給分類器的每個動作上都會失敗。

從 Claude Code v2.1.181 開始，當請求通過自訂基礎 URL 路由時，該區塊在對話的生命週期內是穩定的，因此以完整請求體為鍵的 gateway 端提示快取可以在不禁用它的情況下工作，且您的 gateway 轉發到的任何提供者都會接收穩定的提示前綴。在 v2.1.181 之前，該區塊包含每個請求的令牌，在請求的開始處改變了系統提示。在這些版本上，當您的 gateway 執行以下任一操作時，請設定 `CLAUDE_CODE_ATTRIBUTION_HEADER=0`：

* 實現以請求體為鍵的提示快取。
* 將請求轉發到第三方提供者，例如 Amazon Bedrock、Microsoft Foundry 或 Google Cloud 的 Agent Platform，採用 Anthropic Messages 格式或提供者自己的格式，其中變化的前綴會減少該提供者上的提示快取重複使用。

## 功能傳遞

Claude Code 將 `ANTHROPIC_BASE_URL` gateway 視為 Anthropic 格式端點，並向其發送它發送給 `api.anthropic.com` 的測試版標頭和請求體欄位，除了為直接連接保留的一小組診斷和預設值，例如下面涵蓋的細粒度工具串流預設。該集合因版本而異，因此不要依賴其內容。

細粒度工具串流是直接連接預設值之一：每當請求通過自訂基礎 URL 路由時，它預設為關閉，當開發人員設定 [`CLAUDE_CODE_ENABLE_FINE_GRAINED_TOOL_STREAMING=1`](https://code.claude.com/docs/zh-TW/env-vars) 時，gateway 會接收它。

### 測試版標頭和請求體欄位配對

添加請求體欄位的功能將它們與測試版標頭配對，該對一起傳遞。移除標頭同時傳遞請求體的閘道，或將 Anthropic 格式請求體轉發到具有不同 schema 的上游，會產生 `400` 錯誤。當兩個部分一起不存在時，功能會安靜地關閉。

重寫或編輯請求體以進行內容檢查的閘道會以與移除相同的方式破壞配對，因此請在不修改的情況下檢查。該表注意了功能偏離配對的位置。

| 功能 | 標頭和請求體對 | 破壞時的症狀 | 補救 |
| :- | :- | :- | :- |
| [自適應推理](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) | 無測試版標頭。Claude Code 為 Claude Opus 4.6、Claude Sonnet 4.6、Claude Haiku 5.5、Claude Fable 5 及更新的模型發送 `thinking: {"type": "adaptive"}`，並將它不識別的模型名稱（如閘道別名）視為接收該欄位的目前模型 | 當上游模型建置不接受它時，命名 `thinking` 欄位或 `adaptive` 標籤的 `400` | 升級上游。在 Opus 4.6 和 Sonnet 4.6 上，開發人員可以改為設定 `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1` |
| [上下文管理](https://platform.claude.com/docs/en/build-with-claude/context-editing) | 上下文管理測試版標頭與 `context_management` 請求體欄位配對 | `400` 搭配 `Extra inputs are not permitted`。常見於閘道接受 Anthropic 格式請求但將其轉發到 Amazon Bedrock 時。在 v2.1.304 或更新版本上，Claude Code 會[自行在不含該配對的情況下重試](#automatic-retry-and-error-forwarding) | 轉發兩者，或 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`](#disable-pre-release-capabilities) |
| [擴展上下文](https://platform.claude.com/docs/en/build-with-claude/context-windows#context-window-sizes-by-model)和[交錯思考](https://platform.claude.com/docs/en/build-with-claude/extended-thinking#interleaved-thinking) | 僅測試版標頭，無請求體欄位 | 當標頭被移除時無聲地不可用；上游永遠不會看到功能請求 | 逐字轉發 `anthropic-beta` |
| 測試版[工具欄位](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview) | 工具相關的測試版標頭與工具 schema 欄位（如 `strict` 和 `defer_loading`）配對 | 當請求體在沒有其標頭的情況下通過時，命名無法識別的工具 schema 欄位的 `400`。關於 `defer_loading`，請參閱[不使用工具搜尋重試](#retry-without-tool-search) | 轉發兩者，或 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`](#disable-pre-release-capabilities) |
| [努力](https://platform.claude.com/docs/en/build-with-claude/effort)和[結構化輸出](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | `output_config` 請求體欄位攜帶努力、結構化輸出格式和任務預算設定；每個都與其自己的測試版標頭配對 | 在 Amazon Bedrock 和 Google Cloud 的 Agent Platform 上游上命名 `output_config` 的 `400`，通常是 `Extra inputs are not permitted` | 一起轉發欄位及其標頭，或讓開發人員設定 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`](#disable-pre-release-capabilities)，這會移除格式和任務預算設定，但不會移除努力。若只要移除格式，他們可以改為設定 [`CLAUDE_CODE_DISABLE_STRUCTURED_OUTPUTS=1`](https://code.claude.com/docs/zh-TW/env-vars)，這需要 v2.1.288 或更新版本 |
| 對話中途的系統訊息 | 無測試版標頭。Claude Code 針對 Claude Opus 4.8、在其之後發布的模型以及無法識別的模型 ID，將部分提醒和附件文字作為 `messages` 中的 `role: "system"` 項目發送 | `400`，例如 `Unexpected role "system"` | Claude Code 會[在不含系統訊息的情況下重試](#automatic-retry-and-error-forwarding)。若要在 Claude Opus 4.8 之前發布之模型的別名上停止系統訊息，請在您分發的設定中新增 [`modelOverrides` 項目](#settings-for-unrecognized-model-ids) |
| [每回合設定的努力](https://code.claude.com/docs/zh-TW/prompt-caching.md#changing-effort-level) | 在 Opus 5.5、Sonnet 5.5、Haiku 5.5 和 Fable 5.1 上，測試版標頭與 `role: "system"` 項目上的 `output_config.effort` 配對，該項目可以是系統訊息，也可以是內容為空的項目 | 當您的閘道從空項目中移除該欄位時，出現 `400` 並顯示 `messages.N: system content must contain at least one block` | 轉發兩者，或讓開發人員設定 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`](#disable-pre-release-capabilities) 以停止發送該欄位和空項目 |
| [提示詞快取](https://code.claude.com/docs/zh-TW/prompt-caching.md) | 無測試版配對。Claude Code 將 `cache_control` 標記附加到 `system` 區塊和 `messages` 項目，包括在對話中途附加的 `role: "system"` 項目 | 無錯誤：對話在每個回合上都計費為未快取的輸入，在 `usage` 中可見為高 `input_tokens` 且很少或沒有快取活動 | 無論在何處出現，都逐字轉發 `cache_control`，並且不要將區塊形式的 `system` 或訊息內容轉換為純字串 |
| [令牌計數](https://platform.claude.com/docs/en/build-with-claude/token-counting) | 無測試版配對；使用 `count_tokens` 端點 | 無錯誤：Claude Code 回退到基於字元的估計，因此 `/context` 顯示近似計數 | 公開端點以取得精確令牌計數 |

`ANTHROPIC_DEFAULT_*_MODEL_SUPPORTED_CAPABILITIES` [變數](https://code.claude.com/docs/zh-TW/model-config.md)僅在提供者配置中聲明模型功能：`CLAUDE_CODE_USE_BEDROCK`、`CLAUDE_CODE_USE_VERTEX`、`CLAUDE_CODE_USE_FOUNDRY` 和 [`CLAUDE_CODE_USE_MANTLE`](https://code.claude.com/docs/zh-TW/amazon-bedrock#use-the-mantle-endpoint)。它們在 `ANTHROPIC_BASE_URL` gateway 後面沒有效果。

### 自動重試和錯誤轉發

當上游拒絕其中一項功能時，Claude Code 可以自行在移除或變更被拒絕部分的情況下重試請求：

* 當 `400` 指出不支援 `thinking.type` 值 `enabled` 或 `adaptive` 時，Claude Code 會以另一種類型重試一次，並保留 `thinking` 欄位。在 Claude Code 退出之前，對該模型的後續請求會維持切換後的類型。在 v2.1.121 之前，Claude Code 不會重試，因此 [`thinking.type.enabled is not supported`](https://code.claude.com/docs/zh-TW/errors#thinking-type-enabled-is-not-supported-for-this-model) 會到達開發人員
* 當上游拒絕 `messages` 中的 `role: "system"` 項目時，Claude Code 會在不含這些對話中途系統訊息的情況下重試一次，並改為將其文字放在使用者訊息中。在開發人員執行 `/clear` 或對話壓縮之前，該對話中的後續請求會維持此形式
* 當上游僅拒絕對話中途系統訊息上的 `cache_control` 標記時，Claude Code 會保留系統訊息，並在移動標記後重試一次。在該次重試以及 Claude Code 退出之前的後續請求中，標記會放在 `messages` 中最後一個不是系統訊息的項目上
* 當上游拒絕[思考簽名](https://platform.claude.com/docs/en/build-with-claude/extended-thinking)時，包括以 `400` 拒絕其中區塊 `bound to a different conversation` 時，Claude Code 會從請求中移除較早的思考區塊、重試，並將它們排除在每個後續請求之外。新回應仍包含思考
* 當閘道或其上游將[顧問工具](https://code.claude.com/docs/zh-TW/advisor.md)項目在 `tools` 中拒絕為無法識別的工具類型時，Claude Code 會重試一次請求，不包含該項目及其 `anthropic-beta` 值。[後續請求](#how-long-a-rejected-beta-value-stays-out)會省略它們。Claude Code 透過 `400` 或 `422` 回應識別此拒絕，其訊息在 `Input tag` 後命名工具類型，例如 `Input tag 'advisor_20260301'`。在 v2.1.280 之前，Claude Code 沒有重試此拒絕
* 當上游拒絕 `output_config.effort` 或其 `anthropic-beta` 值時，閘道會再收到一次不含它們的請求。[後續請求](#how-long-a-rejected-beta-value-stays-out)會省略它們。若您的閘道不經修改地轉發上游的 `400`，且其訊息符合以下任一情況，則閘道無需任何變更：
  * 同時命名 `output_config.effort` 和 `Extra inputs are not permitted`
  * 指出該模型不支援努力參數
  * 以 `Unexpected value(s)` 開頭，並針對 `anthropic-beta` 標頭列出 `effort-2025-11-24`。需要 v2.1.310 或更新版本。若開發人員的 [`ANTHROPIC_BETAS`](https://code.claude.com/docs/zh-TW/env-vars) 列出該值，他們會持續發送該值並收到 `400`，因此請讓他們移除該項目
* 當上游拒絕 `context_management` 欄位或其 `anthropic-beta` 值時，閘道會再收到一次不含它們的請求。[後續請求](#how-long-a-rejected-beta-value-stays-out)會省略它們。Claude Code 透過其訊息識別此拒絕，例如包含 `context_management: Extra inputs are not permitted` 的訊息。在 v2.1.304 之前，Claude Code 沒有重試此拒絕
* 當 `400` 依名稱拒絕另一個 `anthropic-beta` 值時，若[該重試涵蓋此值](#retry-without-a-rejected-beta-value)，閘道會再收到一次不含該值的請求
* 當上游拒絕 `defer_loading` 以外的測試版工具欄位（例如 `strict`）時，`400` 會到達開發人員。在此之前，閘道可能會再次收到[不含工具搜尋欄位](#retry-without-tool-search)的請求。若要停止發送這類欄位，請讓開發人員設定 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`](#disable-pre-release-capabilities)

`bound to a different conversation` 拒絕來自 API 的[保留思考](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking)檢查，當 `system`、`tools` 或較早的 `messages` 內容與產生思考的請求不同時，該檢查會失敗。重寫任何該內容的 gateway 可能會導致拒絕本身；[程式庫、代理和 gateway](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking#libraries-proxies-gateways)涵蓋要逐字轉發的內容。

大部分重試邏輯與上游的錯誤措辭相匹配，因此不修改地轉發錯誤回應體。在自己的信封中包裝上游錯誤的閘道會破壞恢復路徑，即使它保留了狀態碼，除非信封的訊息攜帶穩定的 `capability_rejected:` token。[Claude 應用程式閘道為雲端提供者的錯誤措辭替換這些 token](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#upstream-error-messages)，例如 `capability_rejected: prompt_too_long`。

#### 不含被拒絕的測試版值重試

當 `400` 依名稱拒絕此重試所涵蓋的 `anthropic-beta` 值時，閘道會再收到一次不含該值的請求。[後續請求](#how-long-a-rejected-beta-value-stays-out)會省略該值。它涵蓋的大多數值需要 v2.1.314 或更新版本。

若您的閘道所傳回之 `400` 的訊息以下列任一形式攜帶該值，則閘道無需任何變更：

* **API 的句子**：針對 `anthropic-beta` 標頭列出該值的 `Unexpected value(s)` 句子
* **`beta_header:` token**：`capability_rejected: beta_header:` 後接該值，即一種 [`capability_rejected:` token](#automatic-retry-and-error-forwarding)

此重試不涵蓋的情況包括：擁有自己重試機制的值、Claude Code 無法識別的值，或未命名任何值的訊息：

* **擁有自己重試機制的值，例如顧問或工具搜尋**：閘道會改為看到[該功能本身的重試](#automatic-retry-and-error-forwarding)
* **Claude Code 無法識別的值**：開發人員透過 `ANTHROPIC_BETAS` 設定的值會保留在每個請求上，因此開發人員的請求會持續因 `400` 而失敗。請讓開發人員移除該項目
* **單純的 `invalid beta flag`**：Claude Code 會猜測上游拒絕了哪個值。若請求攜帶了它所猜測的值，閘道會再次收到不含該值的請求。若 `400` 仍到達開發人員，請讓您的閘道以上述其中一種形式命名被拒絕的值

#### 被拒絕的測試版值會被排除多久

| 上游拒絕的內容 | 省略它的請求 | 直到 |
| :- | :- | :- |
| 顧問工具類型，或顧問的 `anthropic-beta` 值 | 對相同基礎 URL 的請求。`/advisor` 無法使用 | Claude Code 退出 |
| `output_config.effort` 或其 `anthropic-beta` 值 | 針對相同模型的請求 | Claude Code 退出 |
| `context_management` 或[依名稱重試](#retry-without-a-rejected-beta-value)所涵蓋的其他 `anthropic-beta` 值 | 同一對話中的請求 | 對話結束或 Claude Code 重建其提示詞，例如主對話壓縮時 |
| `context_management` 或該重試所涵蓋的其他值，且錯誤訊息以 API 自身針對拒絕的句子（例如 `Unexpected value(s)`）開頭，或攜帶 `beta_header:` token | 也包括在被拒絕請求所指定之模型上的新對話，包括 `/clear` 之後 | Claude Code 退出 |

#### 不使用工具搜尋重試

在 v2.1.305 或更新版本上，收到命名工具搜尋或 Claude Code 無法識別原因的 `400` 或 `422` 後，Claude Code 會重新發送不含 [`defer_loading` 欄位和 `tool_reference` 區塊](https://code.claude.com/docs/zh-TW/mcp#tool-search-through-a-gateway)的請求。重試成功後，該對話中的後續請求也會省略它們。

開發人員的請求無需對閘道進行任何變更即可繼續運作，其 MCP 工具會預先載入。當 Claude Code 再次嘗試工具搜尋時，閘道可能會看到另一個被拒絕的請求及其後的重試。至於工具搜尋本身，Claude Code 預期閘道會轉送 `defer_loading` 欄位和 `tool_reference` 區塊，以及其 `anthropic-beta` 值。

### 禁用預發佈功能

當您的閘道或其上游拒絕預發佈的 `anthropic-beta` 值或與其配對的請求體欄位，且您無法同時轉發兩個部分時，請讓開發人員設定 `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`。設定該變數後，Claude Code 會停止發送預發佈功能以及與其配對的 `anthropic-beta` 值，包括：

* 上下文管理及其 `context_management` 請求體欄位
* 測試版工具 schema 欄位，例如 `strict` 和 `defer_loading`。標準的 `name`、`description`、`input_schema` 和 `cache_control` 工具欄位會保留
* 結構化輸出的 `output_config.format` 欄位。需要 Claude Code v2.1.287 或更新版本
* `output_config.task_budget` 欄位
* [MCP Tool Search](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search)，因此每個 MCP 工具都會預先載入，除非您的組織透過受管設定將其保持開啟

該變數不會移除所有 `anthropic-beta` 值。它保留的內容包括：

* 擴展上下文、交錯思考和努力的 `anthropic-beta` 值，雲端提供者也接受這些值
* 頂層的 `output_config.effort` 欄位。[自動重試和錯誤轉發](#automatic-retry-and-error-forwarding)涵蓋拒絕它的上游
* 自適應推理的 `thinking` 欄位，它沒有測試版標頭
* 承載[對話中途系統訊息](#feature-pass-through)的 `role: "system"` 項目
* 訂閱身分驗證所需的 OAuth `anthropic-beta` 值
* 開發人員透過 [`ANTHROPIC_BETAS`](https://code.claude.com/docs/zh-TW/env-vars) 或 [`CLAUDE_CODE_EXTRA_BODY`](https://code.claude.com/docs/zh-TW/env-vars) 自行添加的標頭值和請求體欄位

當嵌入 Claude Code 的主機平台設定 [`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`](https://code.claude.com/docs/zh-TW/env-vars) 時，`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS` 不會停止 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 [Claude 應用程式 gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 上的自動模式工作階段要求伺服器進行[分類器審查](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)。該審查添加了 `anthropic-beta` 值和 `safeguards` 請求欄位。設定 `CLAUDE_CODE_AUTO_MODE_SERVER=0` 以在那裡停止它。

在 Claude Code v2.1.227 或更新版本上，您的組織可以通過[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)在此變數下保持 [MCP 工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search)開啟。Claude Code 在該覆蓋就位時發送的內容取決於您如何連接：

* 在未使用 HIPAA 設定的直接連接上，或通過設定了 `ANTHROPIC_BASE_URL` 的閘道，Claude Code 繼續發送工具搜尋測試版標頭、`defer_loading` 工具欄位和 `tool_reference` 區塊
* 在雲端提供者上，或通過 [Claude 應用程式 gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 登入，覆蓋沒有效果
* 在[取得 HIPAA 設定](https://code.claude.com/docs/zh-TW/hipaa-setup.md#check-how-developers-sign-in-and-connect)的工作階段中，覆寫沒有效果，且工具搜尋保持關閉

Claude Code 發送的功能集在版本中增長。有關目前的測試版標頭字串，請參閱[測試版標頭參考](https://platform.claude.com/docs/en/api/beta-headers)；針對新的 Claude Code 版本測試您的 gateway，而不是固定到觀察清單。

## 模型發現

當 `ANTHROPIC_BASE_URL` 指向公開 Anthropic Messages 格式的 gateway 時，Claude Code 可以在啟動時查詢 gateway 的 `/v1/models` 端點，並將返回的模型添加到 `/model` 選擇器。如果您或您的管理員在 [`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#modelpicker) 陣容中設定 `replaceBuiltInOptions`，Claude Code 會從選擇器中隱藏發現的模型。

開發人員通過在自己的環境中或通過受管設定設定 [`CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1`](https://code.claude.com/docs/zh-TW/env-vars) 來啟用它。預設情況下發現是關閉的，以便由共享 API 金鑰支持的 gateway 不會向每個使用者公開金鑰可以存取的每個模型。

### 發現何時運行

發現僅適用於 Anthropic Messages 格式。當以下情況時不運行：

* 設定了任何 `CLAUDE_CODE_USE_*` 提供者變數，即使也設定了 `ANTHROPIC_BASE_URL`
* `ANTHROPIC_BASE_URL` 未設定或指向 `api.anthropic.com`

當[非必要流量被關閉](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#turn-off-traffic-outside-the-gateway-path)時，發現仍會運行，因為請求只會進入您的 gateway。在 v2.1.257 之前，當非必要流量被關閉時，發現不會運行。

### 請求和回應

請求是 `GET /v1/models?limit=1000`，超時時間為 3 秒，任何重定向都被視為失敗，因此認證不會洩露給重定向目標。回應緩慢或重定向 `/v1/models` 的 gateway，即使是 `http` 到 `https`，也會無聲地失敗發現；在配置的基礎 URL 處直接提供端點。

若要給緩慢的 gateway 更長的時間，請設定 [`CLAUDE_CODE_GATEWAY_MODEL_DISCOVERY_TIMEOUT_MS`](https://code.claude.com/docs/zh-TW/env-vars#variables)。該變數需要 Claude Code v2.1.269 或更新版本。

Claude Code 使用以下兩個認證標頭發送發現請求，並省略其值無法解析的標頭。發送兩個標頭需要 Claude Code v2.1.248 或更新版本。較早的版本在設定 `ANTHROPIC_AUTH_TOKEN` 時僅發送 `Authorization`，否則僅發送 `x-api-key`。

* `Authorization`：`ANTHROPIC_AUTH_TOKEN` 作為持有人令牌，否則 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/llm-gateway-connect#rotate-credentials-with-apikeyhelper) 值作為持有人令牌。
* `x-api-key`：Claude Code 解析的 API 金鑰，例如 `ANTHROPIC_API_KEY`。當幫助程式值是唯一的認證時，此標頭也會攜帶它，因此該值會在兩個標頭中到達。

Claude Code 也會發送來自 `ANTHROPIC_CUSTOM_HEADERS` 的任何標頭。當自訂標頭具有非空值時，Claude Code 會發送它來代替同名的內建標頭，不區分大小寫地匹配名稱。

當兩個認證標頭的值都無法解析時，Claude Code 會跳過發現，並在 `claude --debug` 工作階段的偵錯日誌中寫入 `[gatewayDiscovery] skipped` 行。如果您僅通過 `ANTHROPIC_CUSTOM_HEADERS` 提供認證，Claude Code 仍會跳過發現。

Claude Code 從回應的 `data` 陣列中的每個條目讀取 `id`、可選的 `display_name` 和可選的 `description`：

```json theme={null}
{
  "data": [
    {
      "id": "claude-sonnet-4-6",
      "display_name": "Claude Sonnet 4.6",
      "description": "Default model for everyday coding tasks"
    },
    { "id": "claude-opus-4-8" }
  ]
}
```

Claude Code 在其 `id` 中的任何位置包含 `claude` 或 `anthropic` 時保留條目，不區分大小寫，並忽略其餘的。提供者前綴的 ID（例如 `vertex_ai/claude-sonnet-4-6` 或 `bedrock/anthropic.claude-sonnet-4-5`）通過篩選器；不包含任何一個子字符串的 ID 則不通過。在 v2.1.223 之前，Claude Code 僅在其 `id` 以 `claude` 或 `anthropic` 開頭時保留條目，這隱藏了提供者前綴的 ID。

### 選擇器條目和快取

選擇器是當開發人員在 Claude Code 中運行 `/model` 時打開的互動式模型清單。每個發現的條目在 gateway 發送與 `id` 不同的條目時使用 `display_name` 作為其名稱。否則，當 Claude Code [識別 `id`](https://code.claude.com/docs/zh-TW/model-config#customize-pinned-model-display-and-capabilities) 時，條目會顯示模型的名稱，當它不識別時顯示 `id`。例如，具有 `id` `my-gateway-claude-sonnet-4-6` 且沒有 `display_name` 的條目顯示為 `Sonnet 4.6`。

發現僅添加 [`availableModels` 受管設定](https://code.claude.com/docs/zh-TW/settings-reference#availablemodels) 允許的模型。

每個條目也會顯示模型的 `description`，折疊為一行。沒有 `description` 的條目改為讀取「來自 gateway」。在 v2.1.257 之前，每個發現的條目都讀取「來自 gateway」。

當發現的 ID 與選擇器中已有的列匹配時，它不會獲得自己的列：

* 相同 ID：發現的 ID 完全匹配現有列的 ID，或兩個 ID 是同一 [Fable](https://code.claude.com/docs/zh-TW/model-config.md#work-with-fable) 版本的拼寫。
* 與內建別名相同的模型：當發現的明確 ID 命名內建別名目前解析到的模型時，選擇器僅顯示別名列。例如，當 `sonnet` 解析為 `claude-sonnet-5-5` 時，發現的 `claude-sonnet-5-5` 會折疊到 `sonnet` 列中，而發現的 `claude-sonnet-5` 仍會獲得自己的列。

結果被快取到 `~/.claude/cache/gateway-models.json`，或在 Windows 上 `%USERPROFILE%\.claude\cache\gateway-models.json`，並在每次啟動時刷新。如果您設定 [`CLAUDE_CONFIG_DIR`](https://code.claude.com/docs/zh-TW/env-vars)，快取會改為位於該目錄下。如果請求失敗或 gateway 未實現 `/v1/models`，選擇器會回退到上次啟動的快取清單或內建模型清單。如果您的 gateway 在不匹配發現篩選器的別名下提供 Claude 模型，開發人員可以使用[模型配置](https://code.claude.com/docs/zh-TW/model-config.md)變數手動添加這些別名。

## 相關資源

有關 gateway 文件集的其餘部分和基礎 API 參考：

* [Gateway 概述](https://code.claude.com/docs/zh-TW/gateways.md)：什麼是 gateway 以及如何在 Claude 應用程式 gateway 和其他產品之間進行選擇
* [其他 LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway)：如何推出您的組織執行的 gateway 以及它如何與 claude.ai 訂閱互動
* [為您的組織推出 LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway-rollout.md)：使用此指南的管理員檢查清單
* [將 Claude Code 連接到 LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md)：每個開發人員的配置和故障排除表
* [測試版標頭參考](https://platform.claude.com/docs/en/api/beta-headers)：目前的 `anthropic-beta` 值集合
* [Messages API](https://platform.claude.com/docs/en/api/messages)：Anthropic 格式 gateway 實現的 API 格式

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/monitoring-usage | lastmod: 2026-11-03 | section: Administration / Usage and costs -->
> 來源：https://code.claude.com/docs/zh-TW/monitoring-usage（官方 zh-TW，lastmod 2026-11-03）｜分類：Administration › Usage and costs｜EN 摘要：Learn how to enable and configure OpenTelemetry for Claude Code.

# 監控

> 了解如何為 Claude Code 啟用和配置 OpenTelemetry。

透過 OpenTelemetry (OTel) 匯出遙測資料，追蹤 Claude Code 在整個組織中的使用情況、成本和工具活動。Claude Code 透過標準指標協議匯出指標作為時間序列資料、透過日誌/事件協議匯出事件，以及可選地[透過 OpenTelemetry 匯出分散式追蹤](#traces-beta)。

> [!NOTE]
>
> 若要了解 Claude API 或 Managed Agents 的相關資訊，請參閱 [OpenTelemetry for the Claude API](https://platform.claude.com/docs/en/manage-claude/opentelemetry)。

## 快速開始

使用環境變數配置 OpenTelemetry：

```bash theme={null}
# 1. 啟用遙測
export CLAUDE_CODE_ENABLE_TELEMETRY=1

# 2. 選擇匯出器（兩者都是可選的 - 僅配置您需要的）
export OTEL_METRICS_EXPORTER=otlp       # 選項：otlp、prometheus、console、none
export OTEL_LOGS_EXPORTER=otlp          # 選項：otlp、console、none

# 3. 配置 OTLP 端點（用於 OTLP 匯出器）
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# 4. 設定身份驗證（如果需要）
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer your-token"

# 5. 用於除錯：減少匯出間隔，並在生產環境中重設它們
export OTEL_METRIC_EXPORT_INTERVAL=10000  # 10 秒（預設：60000ms）
export OTEL_LOGS_EXPORT_INTERVAL=5000     # 5 秒（預設：5000ms）

# 6. 執行 Claude Code
claude
```

若要驗證匯出指標的設定，請檢查您的後端是否有 `claude_code.session.count` 指標，Claude Code 會在工作階段啟動時發出此指標。若要驗證僅限日誌的設定，請提交提示並檢查 `claude_code.user_prompt` 事件。

如果沒有任何內容到達，請使用 `claude --debug-file <path>` 啟動 Claude Code，並檢查它寫入該路徑的日誌。Claude Code 會將您配置的匯出器失敗報告為 `[3P telemetry]` 錯誤，其中 3P 表示第三方。以 `[Anthropic telemetry]` 為前綴的行描述 [Anthropic 的獨立營運遙測](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services)，不表示您的設定有問題。

如需完整配置選項，請參閱 [OpenTelemetry 規範](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/protocol/exporter.md#configuration-options)。

## 管理員配置

管理員可以透過[受管設定檔](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)為所有使用者配置 OpenTelemetry 設定。請參閱[設定優先順序](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)以了解有關如何應用設定的更多資訊。

受管設定配置範例：

```json theme={null}
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector.example.com:4317",
    "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer example-token"
  }
}
```

在 Claude Desktop 應用程式中，Code 標籤工作階段會從[到達每種 Desktop 工作階段的來源](https://code.claude.com/docs/zh-TW/desktop.md#managed-settings)讀取這些受管設定。管理員主控台[資料和隱私設定](https://claude.ai/admin-settings/data-privacy-controls)中**監控**下的 Cowork OpenTelemetry 表單僅適用於 Cowork 工作階段，因此終端 CLI 和 Code 標籤都不會匯出到您在該處設定的收集器。

Claude Code 會忽略儲存庫的 `.claude/settings.json` 和 `.claude/settings.local.json` 中的 [OpenTelemetry 匯出器變數](https://code.claude.com/docs/zh-TW/settings-reference.md#variables-claude-code-ignores-in-env)，因此儲存庫無法使用它們來開啟遙測、選擇其去向或擷取內容。請在受管設定中設定它們，或讓每個開發人員在其 shell 或 `~/.claude/settings.json` 中設定它們。儲存庫仍然可以透過將其匯出器選擇器（例如 `OTEL_LOGS_EXPORTER`）設定為 `none` 來關閉信號，除非受管設定、`--settings` 檔案或您啟動 Claude Code 的環境設定了該變數。

Claude Code 不會將 `OTEL_*` 環境變數傳遞給它產生的子程序，包括 Bash 工具、hooks、MCP 伺服器和語言伺服器。透過 Bash 工具執行的 OpenTelemetry 檢測應用程式不會繼承 Claude Code 的匯出器端點或標頭，因此如果該應用程式需要匯出自己的遙測，請直接在命令中設定這些變數。

### 受管設定如何鎖定 OTLP 目的地

當您在受管設定中設定 `OTEL_EXPORTER_OTLP_*` 變數時，Claude Code 會在啟動時移除衝突的開發人員設定變數，並在偵錯日誌中記錄警告。它移除的內容取決於您設定的變數：

* **端點**：當您設定 `OTEL_EXPORTER_OTLP_ENDPOINT` 時，Claude Code 會移除每個開發人員設定的每個信號端點。開發人員無法將一個信號指向不同的收集器，因此您不需要在受管設定中也設定每個信號的端點變數。
* **協議**：當您設定 `OTEL_EXPORTER_OTLP_PROTOCOL` 時，Claude Code 會移除每個開發人員設定的每個信號協議。
* **認證**：當您設定 `OTEL_EXPORTER_OTLP_HEADERS`、`OTEL_EXPORTER_OTLP_CLIENT_KEY` 或 `OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE` 時，Claude Code 會移除該變數的開發人員設定每個信號版本，加上每個開發人員設定的端點變數（通用或每個信號），因為這些認證否則會到達受管設定未選擇的收集器。
* **匯出器選擇器**：`OTEL_METRICS_EXPORTER`、`OTEL_LOGS_EXPORTER` 和測試版 `OTEL_TRACES_EXPORTER` 遵循正常的每個鍵優先順序。開發人員的設定仍然可以禁用信號或將其切換到控制台匯出器，因此如果您需要鎖定選擇器，也請在受管設定中設定它們。在[管理員來源](https://code.claude.com/docs/zh-TW/managed-settings.md#precedence-within-the-managed-tier)中，`OTEL_LOGS_EXPORTER` 遵循[遙測單位](https://code.claude.com/docs/zh-TW/server-managed-settings.md#per-key-exceptions-across-managed-sources)，而其他兩個選擇器按鍵合併。需要 Claude Code v2.1.223 或更新版本。
* **測試版追蹤端點**：當[詳細測試版追蹤](#traces-beta)啟用時，Claude Code 會將日誌和追蹤匯出到 `BETA_TRACING_ENDPOINT` 而不是透過日誌和追蹤匯出器。因此，Claude Code 會在以下任何受管設定決定任一信號的目的地時移除開發人員設定的 `BETA_TRACING_ENDPOINT`：

  * 通用或日誌/追蹤端點或認證
  * 一個 [`otelHeadersHelper`](https://code.claude.com/docs/zh-TW/settings-reference#otelheadershelper)
  * 日誌或追蹤匯出器選擇器設定為 `none`、`console` 或空白，這些值會將信號保持在收集器之外
  * `CLAUDE_CODE_ENABLE_TELEMETRY` 關閉

  僅限指標的端點或認證不會移除它。在 v2.1.251 之前，開發人員設定的 `BETA_TRACING_ENDPOINT` 會重新導向詳細測試版追蹤匯出的日誌和追蹤，即使受管設定固定了收集器。

Claude Code 不會移除您在受管設定本身中設定的每個信號變數，因此您可以透過在其中設定其變數來將一個信號路由到不同的收集器，如[SIEM 範例](#send-events-to-a-siem)所示。如果您在其中設定每個信號認證，Claude Code 會移除該信號的開發人員設定端點。

此移除行為改變遙測的傳遞位置，而不是 Claude Code 收集的內容。

在 v2.1.217 之前，每個變數獨立遵循每個鍵設定優先順序，因此在使用者設定或 shell 中設定的信號特定端點會將該信號重新導向離開受管收集器。

當桌面應用程式或[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)執行器啟動 Claude Code 並在其提供的環境中命名 OTLP 端點時，Claude Code 會以相同方式固定目的地：啟動器的遙測變數移除開發人員設定的變數，完全如受管設定所做的那樣。Claude Code 不會移除啟動器本身設定的變數。需要 Claude Code v2.1.251 或更新版本。

## 設定詳細資訊

### 常見設定變數

這些變數為所有部署設定匯出器、端點和匯出行為。

如果您設定了每個信號的端點或協議變數，例如 `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`，Claude Code 會改用它而不是該信號的通用變數。如果您設定了每個信號的標頭變數，例如 `OTEL_EXPORTER_OTLP_METRICS_HEADERS`，Claude Code 會將其與該信號的通用 `OTEL_EXPORTER_OTLP_HEADERS` 合併。

在具有受管設定的機器上，請參閱[受管設定如何鎖定 OTLP 目的地](#how-managed-settings-lock-the-otlp-destination)以了解 Claude Code 移除的內容。

| 環境變數 | 說明 | 範例值 |
| - | - | - |
| `CLAUDE_CODE_ENABLE_TELEMETRY` | 啟用遙測收集（必需） | `1` |
| `OTEL_METRICS_EXPORTER` | 指標匯出器類型，以逗號分隔。使用 `none` 停用 | `console`、`otlp`、`prometheus`、`none` |
| `OTEL_LOGS_EXPORTER` | 日誌/事件匯出器類型，以逗號分隔。使用 `none` 停用 | `console`、`otlp`、`none` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | OTLP 匯出器的協議，適用於所有信號。Claude Code 沒有預設協議，因此請為您啟用的每個 `otlp` 匯出器設定此項或信號特定的協議變數 | `grpc`、`http/json`、`http/protobuf` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | 所有信號的 OTLP 收集器端點 | `http://localhost:4317` |
| `OTEL_EXPORTER_OTLP_METRICS_PROTOCOL` | 指標的協議，覆蓋通用設定 | `grpc`、`http/json`、`http/protobuf` |
| `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT` | OTLP 指標端點，覆蓋通用設定 | `http://localhost:4318/v1/metrics` |
| `OTEL_EXPORTER_OTLP_LOGS_PROTOCOL` | 日誌的協議，覆蓋通用設定 | `grpc`、`http/json`、`http/protobuf` |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | OTLP 日誌端點，覆蓋通用設定 | `http://localhost:4318/v1/logs` |
| `OTEL_EXPORTER_OTLP_HEADERS` | OTLP 的驗證標頭 | `Authorization=Bearer token` |
| `OTEL_EXPORTER_OTLP_METRICS_HEADERS` | 指標的驗證標頭，與通用標頭合併 | `Authorization=Bearer token` |
| `OTEL_EXPORTER_OTLP_LOGS_HEADERS` | 日誌的驗證標頭，與通用標頭合併 | `Authorization=Bearer token` |
| `OTEL_METRIC_EXPORT_INTERVAL` | 匯出間隔（毫秒）（預設值：60000） | `5000`、`60000` |
| `OTEL_LOGS_EXPORT_INTERVAL` | 日誌匯出間隔（毫秒）（預設值：5000） | `1000`、`10000` |
| `OTEL_LOG_USER_PROMPTS` | 啟用使用者提示內容的日誌記錄（預設值：停用） | `1` 啟用 |
| `OTEL_LOG_ASSISTANT_RESPONSES` | 在 `assistant_response` 事件上啟用助手回應文字的日誌記錄（預設值：停用）。未設定時，回退到 `OTEL_LOG_USER_PROMPTS` 的值 | `1` 啟用，`0` 保持編輯 |
| `OTEL_LOG_TOOL_DETAILS` | 在工具事件和追蹤跨度屬性中啟用工具參數和輸入引數的日誌記錄：Bash 命令、MCP 伺服器和工具名稱、技能名稱、使用者撰寫的工作流程名稱和工具輸入。也在 `user_prompt` 事件上啟用自訂、外掛程式和 MCP 命令名稱，以及在[成本和令牌計數器](#cost-counter)上啟用真實代理、技能、外掛程式和 MCP 伺服器和工具名稱（預設值：停用）。對於 Claude Desktop 的內建伺服器，在 Claude Desktop 擁有的工作階段中，即使關閉旗標，`mcp_server_name`/`mcp_tool_name` 也會在 `tool_decision`/`tool_result` 上發出。例外需要 Claude Code v2.1.214 或更新版本 | `1` 啟用 |
| `OTEL_LOG_TOOL_CONTENT` | 在 [`tool.output` 跨度事件](#tool-output-span-event)中啟用工具內容的日誌記錄（預設值：停用）。跨度屬性在[其自己的閘門](#new-context-gates)下攜帶工具內容。需要[追蹤](#traces-beta)。內容在內容限制處截斷（預設值 60 KB） | `1` 啟用 |
| `OTEL_LOG_MANAGED_SETTINGS` | 將編輯的受管設定和設定編輯前的 SHA-256 摘要新增至[受管設定已解決](#managed-settings-resolved-event)事件（預設值：停用）。專案或本機設定中的值不會將其開啟。需要 Claude Code v2.1.274 或更新版本 | `1` 啟用 |
| `OTEL_LOG_RAW_API_BODIES` | 將完整的 Anthropic Messages API 請求和回應 JSON 作為 `api_request_body` / `api_response_body` 日誌事件發出（預設值：停用）。主體包括整個對話歷史記錄。啟用此項意味著同意 `OTEL_LOG_USER_PROMPTS`、`OTEL_LOG_TOOL_DETAILS` 和 `OTEL_LOG_TOOL_CONTENT` 會揭露的所有內容 | `1` 用於在內容限制處截斷的內聯主體（預設值 60 KB），或 `file:<dir>` 用於磁碟上的未截斷主體，在事件中帶有 `body_ref` 指標 |
| `CLAUDE_CODE_OTEL_CONTENT_MAX_LENGTH` | 內容限制：內容承載屬性（例如模型回應、工具內容、系統提示詞和原始 API 主體）的最大長度，包括截斷標記，以 UTF-16 程式碼單位計（預設值：61440，即 60 KB）。預設值適用於將屬性值上限設為 64 KB 的後端；只有在您的後端接受更大的值時才提高它，或降低它以減少遙測量。當設定了 OpenTelemetry SDK 屬性限制 `OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT` 或其日誌記錄和跨度變體之一且其值較小時，Claude Code 會在該較小的值處截斷，以便 `[TRUNCATED ...]` 標記保持在 SDK 限制內 | `262144` |
| `OTEL_EXPORTER_OTLP_METRICS_TEMPORALITY_PREFERENCE` | 指標時間性偏好（預設值：`delta`）。如果您的後端期望累積時間性，請設定為 `cumulative` | `delta`、`cumulative` |
| `CLAUDE_CODE_OTEL_HEADERS_HELPER_DEBOUNCE_MS` | 重新整理動態標頭的間隔（預設值：1740000ms / 29 分鐘） | `900000` |

對於 `http/protobuf` 和 `http/json` 協議，Claude Code 會使用 `Content-Length` 標頭傳送每個匯出請求。

### mTLS 驗證

您如何為 OTLP 匯出器設定用戶端憑證取決於用於該信號的 OTLP 協議，透過 `OTEL_EXPORTER_OTLP_PROTOCOL` 或每個信號的覆蓋設定。相同的設定適用於指標、日誌和追蹤。

| 協議 | 用戶端憑證變數 | 信任收集器的 CA 使用 |
| :- | :- | :- |
| `http/protobuf`、`http/json` | `CLAUDE_CODE_CLIENT_CERT`、`CLAUDE_CODE_CLIENT_KEY` 和選擇性的 `CLAUDE_CODE_CLIENT_KEY_PASSPHRASE`。請參閱[網路設定](https://code.claude.com/docs/zh-TW/network-config.md#mtls-authentication) | `NODE_EXTRA_CA_CERTS` |
| `grpc` | `OTEL_EXPORTER_OTLP_CLIENT_KEY` 和 `OTEL_EXPORTER_OTLP_CLIENT_CERTIFICATE`，或每個信號的變體，例如 `OTEL_EXPORTER_OTLP_METRICS_CLIENT_KEY` 以針對每個信號使用不同的憑證 | `OTEL_EXPORTER_OTLP_CERTIFICATE` |

對於 `grpc`，OpenTelemetry SDK 直接讀取標準 OTLP 變數，因此設定每個信號指標變數的現有設定會繼續運作。在具有受管設定的機器上，Claude Code [可能在啟動時移除開發人員設定的每個信號認證和端點](#how-managed-settings-lock-the-otlp-destination)。

### 指標基數控制

以下環境變數控制指標中包含哪些屬性以管理基數：

| 環境變數 | 說明 | 預設值 | 停用範例 |
| - | - | - | - |
| `OTEL_METRICS_INCLUDE_SESSION_ID` | 在指標中包含 session.id 和（在雲端工作階段上）ccr.session.id 屬性 | `true` | `false` |
| `OTEL_METRICS_INCLUDE_VERSION` | 在指標中包含 app.version 屬性 | `false` | `true` |
| `OTEL_METRICS_INCLUDE_ACCOUNT_UUID` | 在指標中包含 user.account\_uuid 和 user.account\_id 屬性 | `true` | `false` |
| `OTEL_METRICS_INCLUDE_ENTRYPOINT` | 在指標中包含 app.entrypoint 屬性 | `false` | `true` |
| `OTEL_METRICS_INCLUDE_RESOURCE_ATTRIBUTES` | 將 `OTEL_RESOURCE_ATTRIBUTES` 中的金鑰作為屬性包含在指標資料點上 | `true` | `false` |
| `OTEL_METRICS_INCLUDE_REPOSITORY` | 在指標和事件上包含 `vcs.*` [儲存庫身分屬性](#repository-attributes)。需要 Claude Code v2.1.269 或更新版本 | `false` | `true` |

較低的基數通常意味著更好的效能和更低的儲存成本，但分析的資料粒度較低。

### Traces（測試版）

分散式追蹤匯出跨度，將每個使用者提示連結到它觸發的 API 請求和工具執行，因此您可以在追蹤後端中將完整請求檢視為單一追蹤。

追蹤預設為關閉。若要啟用它，請同時設定 `CLAUDE_CODE_ENABLE_TELEMETRY=1` 和 `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`，然後設定 `OTEL_TRACES_EXPORTER` 以選擇跨度的傳送位置。追蹤重複使用[常見 OTLP 設定](#common-configuration-variables)以取得端點、協議、標頭和 [mTLS](#mtls-authentication)。在具有受管設定的機器上，Claude Code [可能在啟動時移除開發人員設定的每個信號認證和端點](#how-managed-settings-lock-the-otlp-destination)。

| 環境變數 | 說明 | 範例值 |
| - | - | - |
| `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA` | 啟用跨度追蹤（必需）。也接受 `ENABLE_ENHANCED_TELEMETRY_BETA` | `1` |
| `OTEL_TRACES_EXPORTER` | 追蹤匯出器類型，以逗號分隔。使用 `none` 停用 | `console`、`otlp`、`none` |
| `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL` | 追蹤的協議，覆蓋 `OTEL_EXPORTER_OTLP_PROTOCOL` | `grpc`、`http/json`、`http/protobuf` |
| `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` | OTLP 追蹤端點，覆蓋 `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4318/v1/traces` |
| `OTEL_EXPORTER_OTLP_TRACES_HEADERS` | 追蹤的驗證標頭，與 `OTEL_EXPORTER_OTLP_HEADERS` 合併 | `Authorization=Bearer token` |
| `OTEL_TRACES_EXPORT_INTERVAL` | 跨度批次匯出間隔（毫秒）（預設值：5000） | `1000`、`10000` |

跨度預設會編輯使用者提示文字、工具輸入詳細資訊和工具內容。設定 `OTEL_LOG_USER_PROMPTS=1`、`OTEL_LOG_TOOL_DETAILS=1` 和 `OTEL_LOG_TOOL_CONTENT=1` 以包含它們。

當追蹤處於作用中時，Bash 和 PowerShell 子程序會自動繼承包含作用中工具執行跨度的 W3C 追蹤內容的 `TRACEPARENT` 環境變數。這讓任何讀取 `TRACEPARENT` 的子程序都可以在相同追蹤下將其自己的跨度作為父項，啟用透過 Claude 執行的指令碼和命令的端對端分散式追蹤。

當追蹤處於作用中且 Claude Code 直接連線到 Anthropic API 時，每個模型請求都會攜帶設定為 `claude_code.llm_request` 跨度內容的 W3C `traceparent` 標頭，API 的 `traceresponse` 標頭會記錄為跨度連結。這些一起透過任何相容的中介將 Claude Code 的用戶端跨度連線到伺服器端追蹤。出站 HTTP MCP 請求以相同方式攜帶 `traceparent`。標頭不會傳送給第三方提供者。

預設情況下，模型和 HTTP MCP 請求上的 `traceparent` 標頭僅在 `ANTHROPIC_BASE_URL` 未設定或指向 Anthropic API 時傳送，因為某些代理會拒絕無法識別的標頭。子程序 `TRACEPARENT` 變數由相同的開關控制以保持一致性。如果您透過自訂 `ANTHROPIC_BASE_URL` 代理執行 Claude Code 並想要傳播追蹤內容，請設定 `CLAUDE_CODE_PROPAGATE_TRACEPARENT=1`。

在 Agent SDK 和使用 `-p` 啟動的非互動式工作階段中，Claude Code 也會在啟動每個互動跨度時從其自己的環境讀取 `TRACEPARENT` 和 `TRACESTATE`。這讓嵌入程序將其作用中的 W3C 追蹤內容傳遞到子程序中，以便 Claude Code 的跨度顯示為呼叫者分散式追蹤的子項。互動式工作階段會忽略入站 `TRACEPARENT` 以避免意外繼承來自 CI 或容器環境的環境值。

入站追蹤內容也適用於[事件](#events)。在設定了 `TRACEPARENT` 的 Agent SDK 和 `-p` 工作階段中，每個 OTLP 事件日誌記錄都會攜帶 `trace_id` 和 `span_id` 值，將其連結到您的應用程式追蹤，即使未設定追蹤匯出器，您的日誌後端也可以將事件與追蹤的其餘部分相關聯。

在互動跨度作用中時發出的記錄會攜帶互動跨度的 ID，即使 Claude Code 在跨度的非同步內容外發出它，例如在權限提示回呼或在啟動期間緩衝並稍後匯出的記錄中。在沒有作用中互動跨度的情況下發出的記錄會直接攜帶入站 `TRACEPARENT` ID。

#### 跨度階層

每個使用者提示啟動一個 `claude_code.interaction` 根跨度。API 呼叫、工具呼叫和 hook 執行會記錄為其子項。工具跨度有兩個自己的子跨度：一個用於等待權限決定所花費的時間，一個用於執行本身。當 Agent 工具或舊版 Task 工具產生子代理時，子代理的 API 和工具跨度會巢狀在父項的 `claude_code.tool` 跨度下。

```text theme={null}
claude_code.interaction
├── claude_code.llm_request
├── claude_code.hook                    (requires detailed beta tracing)
└── claude_code.tool
    ├── claude_code.tool.blocked_on_user
    ├── claude_code.tool.execution
    └── (Agent tool) subagent claude_code.llm_request / claude_code.tool spans
```

在 Agent SDK 和 `claude -p` 工作階段中，當環境中設定了 `TRACEPARENT` 時，`claude_code.interaction` 本身會成為呼叫者跨度的子項。

當 `PreToolUse` hook [延遲工具呼叫](https://code.claude.com/docs/zh-TW/hooks.md#defer-a-tool-call-for-later)時，Claude Code 會儲存延遲它的轉向的追蹤內容。當您恢復工作階段且工具重新執行時，工具的跨度會作為該較早轉向的 `claude_code.interaction` 跨度的子項加入該較早轉向的追蹤。

#### 跨度屬性

每個跨度都會攜帶[標準屬性](#standard-attributes)加上與其名稱相符的 `span.type` 屬性。下表列出在每個跨度上設定的其他屬性。`llm_request`、`tool.execution` 和 `hook` 跨度在記錄失敗時設定 OpenTelemetry 狀態 `ERROR`；其他跨度始終以狀態 `UNSET` 結束。

**`claude_code.interaction`**

| 屬性 | 說明 | 由以下閘門控制 |
| - | - | - |
| `user_prompt` | 提示文字。除非設定了閘門，否則值為 `<REDACTED>` | `OTEL_LOG_USER_PROMPTS` |
| `user_prompt_length` | 提示長度（字元） | |
| `interaction.sequence` | 互動的 1 為基礎計數器，按 Claude Code 程序而不是按工作階段計數，如 [`event.sequence`](#event-correlation-attributes) 所述 | |
| `parent.source` | 跨度如何獲得其追蹤父項：當它在入站 `TRACEPARENT` 下作為父項時為 `env`，當它啟動自己的追蹤時為 `none`。需要 Claude Code v2.1.268 或更新版本 | |
| `interaction.duration_ms` | 轉向的掛鐘持續時間 | |

**`claude_code.llm_request`**

| 屬性 | 說明 | 由以下閘門控制 |
| - | - | - |
| `model` | 模型識別碼 | |
| `gen_ai.system` | 始終為 `anthropic`。OpenTelemetry GenAI 語義慣例 | |
| `gen_ai.request.model` | 與 `model` 相同的值。OpenTelemetry GenAI 語義慣例 | |
| `query_source` | 發出請求的子系統，例如 `repl_main_thread` 或子代理名稱 | `ENABLE_BETA_TRACING_DETAILED` |
| `query_source_safe` | `query_source` 的有界形式，無論詳細測試版追蹤是否作用中都會發出，具有 `repl_main_thread` 或 `agent.builtin.general-purpose` 等值。`:` 變成 `.`，使用者命名的代理顯示為 `agent.custom`。需要 Claude Code v2.1.268 或更新版本 | |
| `agent_id` | 發出請求的子代理或隊友的識別碼。在主工作階段上不存在 | |
| `parent_agent_id` | 產生此代理的代理的識別碼。對於主工作階段和直接從其產生的代理不存在 | |
| `workflow.run_id` | 產生此代理的[工作流程](https://code.claude.com/docs/zh-TW/workflows.md)工具執行的執行識別碼，前綴為 `wf_`。對於不是由工作流程產生的代理不存在 | |
| `workflow.name` | 產生此代理的工作流程的名稱。使用者撰寫的名稱會被替換為 `custom`，除非設定了閘門 | `OTEL_LOG_TOOL_DETAILS` |
| `speed` | `fast` 或 `normal` | |
| `effort` | 套用於請求的[努力等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)：`low`、`medium`、`high`、`xhigh` 或 `max`。當 Claude Code 不傳送努力等級時不存在，例如在不支援努力的模型上。需要 Claude Code v2.1.274 或更新版本 | |
| `llm_request.context` | `interaction`、`tool` 或 `standalone`，取決於父跨度 | |
| `duration_ms` | 包括重試的掛鐘持續時間 | |
| `ttft_ms` | 首個令牌的時間（毫秒） | |
| `first_content_ms` | 從請求開始到成功嘗試的第一個內容區塊的時間（毫秒）。在回退到非串流路徑的請求上不存在。需要 Claude Code v2.1.268 或更新版本 | |
| `input_tokens` | 來自 API 使用區塊的輸入 token 計數。不包括從提示詞快取讀取或寫入提示詞快取的 token，這些會在 `cache_read_tokens` 和 `cache_creation_tokens` 中報告 | |
| `output_tokens` | 輸出令牌計數 | |
| `cache_read_tokens` | 從提示快取讀取的令牌 | |
| `cache_creation_tokens` | 寫入提示快取的令牌 | |
| `request_id` | API 請求 ID。與 `request_id` [事件相關屬性](#event-correlation-attributes)相同的值 | |
| `gen_ai.response.id` | 與 `request_id` 相同的值。OpenTelemetry GenAI 語義慣例 | |
| `client_request_id` | 最終嘗試的用戶端產生的 `x-client-request-id` | |
| `attempt` | 為此請求進行的總嘗試次數 | |
| `success` | `true` 或 `false` | |
| `status_code` | 請求失敗時的 HTTP 狀態碼 | |
| `error` | 請求失敗時的錯誤訊息 | |
| `error_class` | 請求失敗時的簡短錯誤類別令牌，例如 `api_timeout` 或 `server_overload`。需要 Claude Code v2.1.268 或更新版本 | |
| `response.has_tool_call` | 當回應包含工具使用區塊時為 `true` | |
| `stop_reason` | API 回應 `stop_reason`，例如 `end_turn`、`tool_use`、`max_tokens`、`stop_sequence`、`pause_turn` 或 `refusal` | |
| `gen_ai.response.finish_reasons` | 與 `stop_reason` 相同的值，包裝在字串陣列中。OpenTelemetry GenAI 語義慣例 | |

每次重試嘗試也會記錄為具有 `attempt` 和 `client_request_id` 屬性的 `gen_ai.request.attempt` 跨度事件。

**`claude_code.tool`**

| 屬性 | 說明 | 由以下閘門控制 |
| - | - | - |
| `tool_name` | 工具名稱 | |
| `tool_name_safe` | `tool_name` 的形式，不攜帶任何使用者選擇的名稱。內建工具名稱逐字傳遞。MCP 工具名稱顯示為 `mcp_other`，除了符合幾個固定形狀的工具名稱，例如名為 `browser_*` 的 `playwright` 工具，它們逐字傳遞。需要 Claude Code v2.1.268 或更新版本 | |
| `bash_command_class` | 對於 Bash 工具：命令的第一個程式的類別，來自固定清單，例如 `vcs` 或 `package_manager`。`other` 用於清單外的程式，`unparsed` 當行無法解析時。需要 Claude Code v2.1.268 或更新版本 | |
| `bash_argv0` | 對於 Bash 工具：當命令的第一個程式在相同的固定清單上時，例如 `git` 或 `npm`。`other` 用於清單外的任何程式。需要 Claude Code v2.1.268 或更新版本 | |
| `duration_ms` | 包括權限等待和執行的掛鐘持續時間 | |
| `result_tokens` | 工具結果的近似令牌大小 | |
| `agent_id` | 執行工具的子代理或隊友的識別碼。在主工作階段上不存在 | |
| `parent_agent_id` | 產生此代理的代理的識別碼。對於主工作階段和直接從其產生的代理不存在 | |
| `workflow.run_id` | 產生此代理的工作流程工具執行的執行識別碼，前綴為 `wf_`。對於不是由工作流程產生的代理不存在 | |
| `workflow.name` | 產生此代理的工作流程的名稱。使用者撰寫的名稱會被替換為 `custom`，除非設定了閘門 | `OTEL_LOG_TOOL_DETAILS` |
| `tool_use_id` | 此呼叫的模型 `tool_use` 區塊 id。與 [tool\_result](#tool-result-event) 和 [tool\_decision](#tool-decision-event) 事件上的 `tool_use_id` 以及 hook 承載中的相符，因此您可以將跨度連結到這些記錄 | |
| `gen_ai.tool.call.id` | 與 `tool_use_id` 相同的值。OpenTelemetry GenAI 語義慣例 | |
| `file_path` | Read、Edit 和 Write 工具的目標檔案路徑 | `OTEL_LOG_TOOL_DETAILS` |
| `full_command` | Bash 工具的命令字串 | `OTEL_LOG_TOOL_DETAILS` |
| `skill_name` | Skill 工具的技能名稱 | `OTEL_LOG_TOOL_DETAILS` |
| `subagent_type` | Agent 工具或舊版 Task 工具的子代理類型 | `OTEL_LOG_TOOL_DETAILS` |

**`claude_code.tool` 上的 `tool.output` 跨度事件**

如果您設定 `OTEL_LOG_TOOL_CONTENT=1`，Read 和 Bash 呼叫可以在 `claude_code.tool` 跨度上記錄 `tool.output` 跨度事件。Edit 和 Write 呼叫只有在您也設定 `OTEL_LOG_TOOL_DETAILS=1` 時才會記錄一個。該變數不限於這兩個工具，因此請檢查其[設定表中的列](#common-configuration-variables)以了解它在其他地方新增的引數。

MCP 工具、WebFetch 和 WebSearch 也會記錄此事件，在 Claude Code v2.1.283 或更新版本上。

Claude Code 從工具呼叫的成功返回時寫入此事件，因此引發錯誤的呼叫不會記錄任何內容，無論工具如何。在確實返回的呼叫中，它不會為以下內容記錄 `tool.output` 事件：

* 呼叫 Read、Edit、Write、Bash、WebFetch、WebSearch 和 MCP 工具以外的任何工具
* 返回檔案文字以外的任何內容的 Read，例如影片、PDF 或檔案內容未變更的重新讀取
* Edit 或 Write 呼叫，除非您也設定 `OTEL_LOG_TOOL_DETAILS=1`
* Claude Code 在執行期間將其移至背景，以便等待中的訊息能夠傳達給 Claude 的 WebFetch 或 WebSearch 呼叫。稍後到達的結果也不會被記錄。若要了解 Claude Code 何時移動呼叫，請參閱終端機的[Claude Code 何時傳送您佇列的內容](https://code.claude.com/docs/zh-TW/interactive-mode.md#when-claude-code-sends-what-you-queued)，以及 Agent SDK 工作階段的 [`priority` 欄位](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkusermessage)

該事件攜帶這些屬性，每個都在內容限制處截斷（預設值 60 KB）。`由以下閘門控制` 命名屬性在 `OTEL_LOG_TOOL_CONTENT=1` 之上需要的變數，對於 Edit 和 Write，該變數控制事件本身而不是屬性。

| 屬性 | 說明 | 由以下閘門控制 |
| - | - | - |
| `content` | Read 工具返回的文字，或 Write 呼叫被要求寫入的文字 | Write 工具的 `OTEL_LOG_TOOL_DETAILS` |
| `output` | 對於 Bash 工具，命令的組合輸出，stderr 交錯到 stdout。對於 MCP 工具、WebFetch 或 WebSearch，工具返回的結果：文字區塊由換行符連結，影片或文件被替換為 `[image]` 等佔位符 | |
| `diff` | Edit 工具套用的結構化修補程式 | `OTEL_LOG_TOOL_DETAILS` |
| `file_path` | Read、Edit 和 Write 工具的目標檔案路徑，重複跨度屬性的相同名稱 | `OTEL_LOG_TOOL_DETAILS` |
| `bash_command` | Bash 工具的命令字串 | `OTEL_LOG_TOOL_DETAILS` |

父跨度的 `tool_name` 屬性告訴您事件來自哪個工具。在內容限制處切割的屬性伴隨著 `<attribute>_truncated` 和 `<attribute>_original_length`。

**`claude_code.tool.blocked_on_user`**

| 屬性 | 說明 | 由以下閘門控制 |
| - | - | - |
| `duration_ms` | 等待權限決定所花費的時間 | |
| `decision` | `accept`、`reject` 或 `cancelled`，其中 `cancelled` 表示 Claude Code 停止等待該工具呼叫的權限決定，且未執行該工具呼叫 | |
| `source` | 對於 `accept` 或 `reject`，表示決定的來源，例如 `config`、`hook` 或 `user_temporary`，其含義如[工具決定事件](#tool-decision-event)所述。對於 `cancelled`，表示在做出任何決定之前結束等待的原因，例如 `user_abort` | |

`source` 為 `user_abort` 的 `cancelled` 決定，表示在權限提示或[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)檢查仍待處理時，一則需要立即傳遞的訊息中斷了該回合。例如，在自動模式檢查期間，使用者有一則已排入佇列的訊息，並[立即傳送了它](https://code.claude.com/docs/zh-TW/interactive-mode.md#when-claude-code-sends-what-you-queued)。

**`claude_code.tool.execution`**

| 屬性 | 說明 | 由以下閘門控制 |
| - | - | - |
| `duration_ms` | 執行工具主體所花費的時間 | |
| `tool_use_id` | 與父 `claude_code.tool` 跨度上的相同值 | |
| `gen_ai.tool.call.id` | 與 `tool_use_id` 相同的值。OpenTelemetry GenAI 語義慣例 | |
| `success` | `true` 或 `false` | |
| `error` | 執行失敗時的錯誤類別字串，例如 `Error:ENOENT` 或 `ShellError`。當設定了閘門時包含完整的錯誤訊息 | `OTEL_LOG_TOOL_DETAILS` |
| `error_class` | 識別碼形式的錯誤類別，字母、數字和底線以外的字元被替換為 `_`，例如 `Error_ENOENT` 或 `ShellError`。即使 `error` 攜帶完整訊息也會攜帶類別。需要 Claude Code v2.1.268 或更新版本 | |

**`claude_code.hook`**

此跨度僅在詳細測試版追蹤作用中時出現，這需要 `ENABLE_BETA_TRACING_DETAILED=1` 和 `BETA_TRACING_ENDPOINT`，一對也[變更日誌和追蹤的去向](https://code.claude.com/docs/zh-TW/env-vars.md#variables)。在您的殼層、使用者設定或受管設定中設定該對；兩個變數都在[專案和本機設定](https://code.claude.com/docs/zh-TW/settings-reference.md#variables-claude-code-ignores-in-env)中被忽略。`CLAUDE_CODE_ENHANCED_TELEMETRY_BETA` 單獨不會產生它。

在互動式 CLI 工作階段中，詳細測試版追蹤也需要您的組織被列入該功能的允許清單。Agent SDK 和非互動式 `-p` 工作階段不需要允許清單。

> [!WARNING]
>
> 僅在除錯時設定 `ENABLE_BETA_TRACING_DETAILED`，請勿在正式環境中設定。詳細測試版追蹤的匯出量很高，且其[內容屬性](#new-context-gates)不屬於穩定跨度 schema 的一部分。

| 屬性 | 說明 | 由以下閘門控制 |
| - | - | - |
| `hook_event` | Hook 事件類型，例如 `PreToolUse` | |
| `hook_name` | 完整 hook 名稱，例如 `PreToolUse:Write` | |
| `num_hooks` | 執行的相符 hook 命令數 | |
| `hook_definitions` | JSON 序列化的 hook 設定 | `OTEL_LOG_TOOL_DETAILS` |
| `duration_ms` | 所有相符 hook 的掛鐘持續時間 | |
| `num_success` | 成功完成的 hook 計數 | |
| `num_blocking` | 返回阻止決定的 hook 計數 | |
| `num_non_blocking_error` | 失敗而不阻止的 hook 計數 | |
| `num_cancelled` | 在完成前取消的 hook 計數 | |

**詳細測試版追蹤下的內容屬性**

> [!NOTE]
>
> 其他內容承載屬性，例如 `new_context`、`system_reminders`、`system_prompt_preview`、`user_system_prompt`、`tool_input` 和 `response.model_output`，僅在詳細測試版追蹤作用中時發出。它們不是穩定跨度 schema 的一部分。

這些屬性出現在以下跨度上，`由以下閘門控制` 命名屬性在詳細測試版追蹤之上需要的變數。長於內容限制（預設值 60 KB）的值會被截斷。

| 屬性 | 跨度 | 說明 | 由以下閘門控制 |
| - | - | - | - |
| `new_context` | `claude_code.interaction` | 使用者提示詞 | `OTEL_LOG_USER_PROMPTS` |
| `new_context` | `claude_code.llm_request` | 隨請求傳送的新使用者訊息和工具結果 | `OTEL_LOG_USER_PROMPTS` |
| `system_reminders` | `claude_code.llm_request` | 請求新訊息中[系統提醒](https://code.claude.com/docs/zh-TW/glossary.md#system-reminder)的文字 | `OTEL_LOG_USER_PROMPTS` |
| `system_prompt_preview` | `claude_code.llm_request` | 隨請求傳送的完整系統提示詞的前 500 個字元 | `OTEL_LOG_USER_PROMPTS` |
| `user_system_prompt` | `claude_code.llm_request` | 僅限您透過 `systemPrompt` SDK 選項或 `--system-prompt` 和 `--append-system-prompt` 旗標提供的系統提示詞文字。每個工作階段發出一次，而不是每個請求 | `OTEL_LOG_USER_PROMPTS` |
| `response.model_output` | `claude_code.llm_request` | 模型對請求的回應文字 | `OTEL_LOG_USER_PROMPTS` |
| `new_context` | `claude_code.tool` | 工具呼叫的結果，無論工具如何 | `OTEL_LOG_TOOL_CONTENT` |
| `tool_input` | `claude_code.tool` | 工具呼叫的序列化輸入 | `OTEL_LOG_TOOL_DETAILS` |

在詳細測試版追蹤下且設定 `OTEL_LOG_USER_PROMPTS=1` 時，Claude Code 也會發出 `claude_code.system_prompt` 事件，攜帶完整的系統提示詞，並在內容限制處截斷。它會在工作階段首次傳送每個不同的系統提示詞時到達，並在壓縮後再次到達。

### 動態標頭

對於需要動態驗證的企業環境，您可以設定指令碼以動態產生標頭。動態標頭僅適用於 `http/protobuf` 和 `http/json` 協議。使用 `grpc` 協議，Claude Code 僅使用靜態標頭變數 `OTEL_EXPORTER_OTLP_HEADERS` 及其每個信號的變體。

#### 設定設定

新增至您的 `.claude/settings.json`，將路徑替換為您自己的指令碼：

```json theme={null}
{
  "otelHeadersHelper": "/path/to/generate-otel-headers.sh"
}
```

該值可以是可執行檔的路徑，包括包含空格的路徑，或帶有引數的殼層命令列。在 Windows 上，該值始終透過殼層執行，因此在 JSON 值內引用包含空格的路徑。

#### 指令碼需求

指令碼必須輸出有效的 JSON，其中包含代表 HTTP 標頭的字串鍵值對：

```bash theme={null}
#!/bin/bash
# Example: Multiple headers
echo "{\"Authorization\": \"Bearer $(get-token.sh)\", \"X-API-Key\": \"$(get-api-key.sh)\"}"
```

如果協助程式失敗或列印不符合這些需求的輸出，匯出會失敗，您的遙測後端在協助程式再次運作之前不會從工作階段接收任何內容。Claude Code 在以下位置報告失敗：

* 互動式工作階段中的警告通知，[`otelHeadersHelper failed; telemetry is not being exported`](https://code.claude.com/docs/zh-TW/errors#otelheadershelper-failed)，在協助程式首次失敗時每個工作階段顯示一次
* `/status` 輸出
* 偵錯日誌，當使用 [`--debug`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 執行或在工作階段中執行 `/debug` 後
* stderr，在使用 `-p` 啟動的非互動式工作階段中

#### 重新整理行為

標頭協助程式指令碼在啟動時執行，之後定期執行以支援令牌重新整理。預設情況下，指令碼每 29 分鐘執行一次。使用 `CLAUDE_CODE_OTEL_HEADERS_HELPER_DEBOUNCE_MS` 環境變數自訂間隔。

### 多團隊組織支援

具有多個團隊或部門的組織可以使用 `OTEL_RESOURCE_ATTRIBUTES` 環境變數新增自訂屬性以區分不同的群組：

```bash theme={null}
# Add custom attributes for team identification
export OTEL_RESOURCE_ATTRIBUTES="department=engineering,team.id=platform,cost_center=eng-123"
```

這些自訂屬性包含在所有指標和事件中，允許您：

* 按團隊或部門篩選指標
* 追蹤每個成本中心的成本
* 建立團隊特定的儀表板
* 為特定團隊設定警示

Claude Code 將這些值作為屬性附加到每個指標資料點和事件記錄，除了在 OTLP 資源區塊中傳送它們。因為大多數指標後端將資料點屬性公開為可查詢的標籤，您可以直接按自訂金鑰分組和篩選指標。除了 `vcs.*` [儲存庫屬性](#repository-attributes)，自訂金鑰永遠不會覆蓋[標準屬性](#standard-attributes)，例如 `user.id` 或 `session.id`：當金鑰衝突時，Claude Code 會保留內建值。

每個自訂金鑰都會成為每個指標系列上的標籤，因此高基數值會增加指標後端中的儲存成本。若要僅在資源區塊中傳送自訂屬性並從資料點標籤中省略它們，請設定 `OTEL_METRICS_INCLUDE_RESOURCE_ATTRIBUTES=false`。請參閱[指標基數控制](#metrics-cardinality-control)。

> [!WARNING]
>
> `OTEL_RESOURCE_ATTRIBUTES` 環境變數使用逗號分隔的鍵值對，具有嚴格的格式要求：
>
> * **不允許空格**：值不能包含空格。例如，`user.organizationName=My Company` 無效
> * **格式**：必須是逗號分隔的鍵值對：`key1=value1,key2=value2`
> * **允許的字元**：僅限 US-ASCII 字元，不包括控制字元、空格、雙引號、逗號、分號和反斜線
> * **特殊字元**：允許範圍外的字元必須進行百分比編碼
>
> 對於需要空格的值，請改用底線或 camelCase。以下範例使用每種形式設定 `org.name`：
>
> ```bash theme={null}
> export OTEL_RESOURCE_ATTRIBUTES="org.name=Johns_Organization"
> export OTEL_RESOURCE_ATTRIBUTES="org.name=JohnsOrganization"
> ```
>
> 您可以百分比編碼任何字元，不僅是排除的字元。此範例對空格和撇號進行編碼：
>
> ```bash theme={null}
> export OTEL_RESOURCE_ATTRIBUTES="org.name=John%27s%20Organization"
> ```
>
> 將值包裝在引號中不會逃脫空格。例如，`org.name="My Company"` 會導致文字值 `"My Company"`（包括引號），而不是 `My Company`。

### 將遙測歸因至 Desktop SSH 工作階段

若要查看 [Desktop SSH 工作階段](https://code.claude.com/docs/zh-TW/desktop.md#ssh-sessions)在哪台遠端機器上執行，請在自訂屬性中為每台機器命名。指標和事件不會指明工作階段執行所在的機器。

在每台遠端機器上，將 [`OTEL_RESOURCE_ATTRIBUTES`](#multi-team-organization-support) 新增至開啟遙測的 `env` 區塊，該區塊位於[工作階段讀取的受管設定檔](https://code.claude.com/docs/zh-TW/desktop.md#managed-settings)中。在每台機器的檔案中直接寫出名稱。Claude Code 不會展開該值，因此 `host.name=$(hostname)` 會以這些字元原樣到達。

以下範例將機器命名為 `build-7`：

```json theme={null}
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector.example.com:4317",
    "OTEL_RESOURCE_ATTRIBUTES": "host.name=build-7"
  }
}
```

當沒有其他項目設定此變數時，`host.name` 會出現在資源區塊中，無論是在 Desktop SSH 工作階段中，或是在該機器上的 CLI 中。關於自訂屬性還會出現在哪些地方，請參閱[多團隊組織支援](#multi-team-organization-support)。

如果名稱沒有到達，請檢查是否為以下原因之一：

* **您在執行 Desktop 的電腦上設定了它**：Desktop 不會將您在該處設定的值傳遞給 SSH 工作階段
* **您在 `/etc/profile` 或其他只有登入 shell 會讀取的檔案中匯出了它**：當您從登入 shell 執行 `claude` 時名稱會到達，但在 Desktop SSH 工作階段中不會。Desktop 不會透過登入 shell 啟動 Claude Code。請改為在遠端機器上的[受管設定檔](https://code.claude.com/docs/zh-TW/desktop.md#managed-settings)中，於 `env` 下設定此變數。
* **值中含有空格**：此時 Claude Code 不會將任何鍵複製到事件或資料點上，也不會回報錯誤。[移除值中的空格](#multi-team-organization-support)。
* **其他項目已設定此變數**：在桌面應用程式啟動的工作階段中，啟動環境中已設定的變數[優先於設定檔](https://code.claude.com/docs/zh-TW/settings-reference.md#how-env-values-interact-with-your-shell)。[除錯日誌](https://code.claude.com/docs/zh-TW/debug-your-config.md)會列出每個被忽略的變數。當第三方 Desktop 部署在其提供的環境中[指定 OTLP 端點](#how-managed-settings-lock-the-otlp-destination)時，該環境會攜帶 Desktop 自己的 `OTEL_RESOURCE_ATTRIBUTES`。

### 範例設定

在執行 `claude` 之前設定這些環境變數。下面的每個案例都顯示完整的設定，每個變數都在[常見設定變數](#common-configuration-variables)下描述。若要確認設定生效，請在啟動工作階段後檢查您的後端是否有 `claude_code.session.count` 指標；[快速入門](#quick-start)涵蓋僅日誌驗證以及當沒有任何內容到達時要檢查的內容。

用於主控台偵錯，匯出間隔為 1 秒：

```bash theme={null}
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=console
export OTEL_METRIC_EXPORT_INTERVAL=1000
```

用於透過 gRPC 的 OTLP：

```bash theme={null}
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

用於 Prometheus，從 `http://localhost:9464/metrics` 抓取：

```bash theme={null}
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=prometheus
```

在[自託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments-reference.md#pass-through-session-child-metrics)上，工作階段僅在執行器的預設容量為 1 時繫結連接埠 9464。在更高的容量下，執行器改為在其自己的 `/metrics` 端點上重新公開工作階段計數器和量表。

若要將指標傳送到多個匯出器：

```bash theme={null}
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=console,otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
```

若要將指標和日誌傳送到不同的端點或後端：

```bash theme={null}
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_METRICS_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=http://metrics.example.com:4318
export OTEL_EXPORTER_OTLP_LOGS_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://logs.example.com:4317
```

若要僅匯出指標，不匯出事件或日誌：

```bash theme={null}
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

若要僅匯出事件和日誌，不匯出指標：

```bash theme={null}
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

## 雲端工作階段和 Claude Tag 的遙測

[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)（包括 [Claude Tag](https://claude.com/docs/claude-tag/overview) 頻道工作階段）在[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)中執行，而不是在使用者的裝置上執行，因此裝置上的受管設定檔或 shell 設定檔不會設定其遙測。對於在 Anthropic 代管環境中的工作階段，本節涵蓋設定遙測變數的位置、如何使收集器可從環境存取，以及如何在匯出的資料中區分雲端和 Claude Tag 工作階段。

若要從這些工作階段匯出遙測，請使用與[管理員設定](#administrator-configuration)範例相同的金鑰，在下列兩個位置之一設定 `CLAUDE_CODE_ENABLE_TELEMETRY` 和 `OTEL_*` 變數：

* **伺服器受管設定**：將它們新增至組織的[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)的 `env` 區塊。Claude Code 在[伺服器受管設定適用](https://code.claude.com/docs/zh-TW/model-config.md#surface-coverage)的任何位置啟動時會擷取這些設定，包括使用者的機器和 Claude Tag 頻道工作階段以外的雲端工作階段。Claude Tag 工作階段不會接收伺服器受管設定，因此此路由不會設定它們。
* **環境的變數**：將它們新增至雲端環境的[環境變數](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-environment-variables)，以僅設定在該環境中執行的工作階段。這是到達 Claude Tag 工作階段的路由。

任何使用環境的人都可以讀取其變數，因此不要在其中放置憑證，例如 `OTEL_EXPORTER_OTLP_HEADERS` 中的收集器 token。環境上的[網路密鑰](https://code.claude.com/docs/zh-TW/cloud-environments.md#add-network-secrets)也無法幫助，因為 Claude Code 自己的遙測匯出是[永遠不會取得密鑰的請求](https://code.claude.com/docs/zh-TW/cloud-environments.md#requests-that-never-get-the-credential)之一。如果收集器需要憑證，請改為透過伺服器受管設定設定整個匯出，因為當您在該處設定憑證時，[Claude Code 會移除在受管設定外設定的端點變數](#how-managed-settings-lock-the-otlp-destination)。

在為雲端工作階段設定遙測時，請記住這些限制：

* **讓工作階段到達收集器**：Claude Code 透過工作階段的網路傳送匯出，因此它是否到達 `OTEL_EXPORTER_OTLP_ENDPOINT` 中的主機取決於環境的[網路存取層級](https://code.claude.com/docs/zh-TW/cloud-environments.md#access-levels)。如果工作階段無法在您選擇的層級到達收集器的網域，請[將網域新增至環境的允許清單](https://code.claude.com/docs/zh-TW/cloud-environments.md#allow-specific-domains)，因為沒有伺服器受管設定會將網域新增至環境的網路允許清單。
* **Claude Tag 頻道**：請在設定為組織預設或釘選到頻道的[共用環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#organization-shared-environments)上進行允許清單和任何環境變數變更。
* **Cowork 單獨設定**：如[表面涵蓋表](https://code.claude.com/docs/zh-TW/model-config.md#surface-coverage)所示，Cowork 工作階段不會接收伺服器受管設定，因此伺服器受管 `env` 區塊不會設定其遙測。

### 將遙測歸因於雲端工作階段

根據預設，來自雲端工作階段的指標和事件會帶有[標準屬性](#standard-attributes)，包括 `session.id`、`ccr.session.id` 和 `organization.id`，因此您可以按工作階段或組織篩選，無需額外設定。`ccr.session.id` 值是工作階段的 `CLAUDE_CODE_REMOTE_SESSION_ID`。若要將其轉換為工作階段的文字記錄 URL，請參閱[將輸出連結回工作階段](https://code.claude.com/docs/zh-TW/cloud-environments.md#link-output-back-to-the-session)。

若要區分雲端工作階段，請依 `ccr.session.id` 而非 `session.id` 進行分組或篩選。

若要更詳細地歸因遙測，請使用這些選項：

* **識別 Claude Tag 工作階段**：設定 `OTEL_METRICS_INCLUDE_ENTRYPOINT=true`，如[指標基數控制](#metrics-cardinality-control)下所述。指標隨後會帶有 `app.entrypoint`，其值對於 Claude Tag 工作階段為 `claude-in-slack`。
* **新增自訂屬性**：在設定這些工作階段的其他 `OTEL_*` 變數的相同位置設定 [`OTEL_RESOURCE_ATTRIBUTES`](#multi-team-organization-support)。如果您改為在環境的[設定指令碼](https://code.claude.com/docs/zh-TW/cloud-environments.md#setup-scripts)中 `export` 它，該值不會到達 Claude Code：設定指令碼是在 Claude Code 啟動前執行的單獨 Bash 指令碼，它匯出的變數會隨著它結束。

在 Claude Tag 頻道工作階段中，Claude 作為組織的[共用身分](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-the-environment-a-claude-tag-channel-uses)而不是任何成員工作，因此不要依賴 `user.*` 屬性來識別誰標記了 Claude。

## 可用的指標與事件

### 標準屬性

所有指標與事件都共用以下標準屬性：

| 屬性 | 說明 | 控制方式 |
| - | - | - |
| `session.id` | Claude Code 自身的工作階段 ID，`/clear` 會將其替換 | `OTEL_METRICS_INCLUDE_SESSION_ID`（預設：true） |
| `ccr.session.id` | 雲端工作階段識別碼，即 `CLAUDE_CODE_REMOTE_SESSION_ID` 的值，出現在於[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md)中執行的工作階段上 | `OTEL_METRICS_INCLUDE_SESSION_ID`（預設：true） |
| `app.version` | 目前的 Claude Code 版本 | `OTEL_METRICS_INCLUDE_VERSION`（預設：false） |
| `app.entrypoint` | 工作階段的啟動方式，例如 `cli`、`sdk-cli`、`sdk-ts`、`sdk-py`、`claude-vscode`，或 Claude Tag 工作階段的 `claude-in-slack` | `OTEL_METRICS_INCLUDE_ENTRYPOINT`（預設：false） |
| `organization.id` | 組織 UUID（已通過身分驗證時） | 可用時一律包含 |
| `user.account_uuid` | 帳戶 UUID（已通過身分驗證時） | `OTEL_METRICS_INCLUDE_ACCOUNT_UUID`（預設：true） |
| `user.account_id` | 符合 Anthropic 管理 API 的標記格式帳戶 ID（已通過身分驗證時），例如 `user_01BWBeN28...` | `OTEL_METRICS_INCLUDE_ACCOUNT_UUID`（預設：true） |
| `user.id` | 首次執行時產生並保存在 `~/.claude.json` 中的隨機匿名識別碼。它不包含任何個人資訊，也並非衍生自您的 Claude 帳戶。刪除該檔案後，下次執行時會產生一個不相關的新值。 | 一律包含 |
| `user.email` | 使用者電子郵件地址，來自您的登入資訊，或在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中來自該工作階段自身的憑證 | 可用時一律包含 |
| `terminal.type` | 終端機類型，例如 `iTerm.app`、`vscode`、`cursor` 或 `tmux` | 偵測到時一律包含 |
| 來自 `OTEL_RESOURCE_ATTRIBUTES` 的鍵 | 您設定的自訂屬性，例如 `department` 或 `team.id`。請參閱[多團隊組織支援](#multi-team-organization-support) | `OTEL_METRICS_INCLUDE_RESOURCE_ATTRIBUTES`（預設：true） |
| `vcs.repository.url.full`、`vcs.owner.name`、`vcs.repository.name`、`vcs.provider.name` | 工作階段儲存庫的識別資訊，衍生自其 `origin` remote。請參閱[儲存庫屬性](#repository-attributes) | `OTEL_METRICS_INCLUDE_REPOSITORY`（預設：false）。需要 Claude Code v2.1.269 或更新版本 |

在透過 `/login` 登入 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)的工作階段中，CLI 會在匯出資料上標記已通過身分驗證的身分：`user.id` 是 IdP subject，`user.email` 是登入的電子郵件，而 `user.groups` 則以逗號分隔字串的形式攜帶 IdP 群組成員資格。每筆匯出也會攜帶 `identity.source: gateway-oidc`。閘道身分最後才套用，因此在這些工作階段中，透過 `OTEL_RESOURCE_ATTRIBUTES` 設定的 `user.*` 與 `identity.*` 鍵會被忽略。

> [!NOTE]
>
> Claude Code 在開發人員登入前記錄的事件不會攜帶閘道身分。當 Claude Code 在未登入閘道的狀態下開啟工作階段時，例如在[閘道結束登入](https://code.claude.com/docs/zh-TW/errors.md#cloud-gateway-session-expired)之後，登入前記錄的啟動事件會攜帶匿名的 `user.id`，且沒有 `identity.source`。這些事件包括 [`managed_settings_resolved`](#managed-settings-resolved-event)、[`plugin_loaded`](#plugin-loaded-event) 與 [`mcp_server_connection`](#mcp-server-connection-event)。

關於透過閘道連線的 Claude Desktop 與 Cowork 工作階段上的身分屬性，請參閱[閘道 `telemetry` 參考](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#telemetry)。

事件還額外包含以下屬性。這些屬性絕不會附加到指標上，因為它們會造成無上限的基數：

* `prompt.id`：將使用者提示詞與其後所有事件（直到下一個提示詞為止）相互關聯的 UUID。請參閱[事件關聯屬性](#event-correlation-attributes)。
* `workspace.host_paths`：在桌面應用程式中選取的主機工作區目錄，以字串陣列表示
* `workflow.run_id`：執行識別碼，以 `wf_` 為前綴，出現在屬於 [Workflow](https://code.claude.com/docs/zh-TW/workflows.md) 工具執行的 agent 所發出的 API 與工具事件上。依單一 `workflow.run_id` 篩選事件，即可重建該次執行的 API 請求與工具結果。此識別碼涵蓋工作流程指令碼所產生的 agent，以及這些 agent 再產生的任何 agent，例如 skill 呼叫。它與 Workflow 工具結果中回報的執行識別碼相符。
* `workflow.name`：工作流程的名稱，即其指令碼的 `meta.name`，與 `workflow.run_id` 一同發出。當執行的是未經修改的內建指令碼時，內建工作流程名稱會原樣顯示。使用者撰寫的名稱（包括內建指令碼的編輯副本）會被替換為 `custom`，除非設定了 `OTEL_LOG_TOOL_DETAILS=1`。
* `agent_id`：引發事件的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 的識別碼，例如 `a3f2c1b4d5e6f7a80`。攜帶此屬性的事件包括 subagent 的 API 與工具事件、其 [`assistant_response`](#assistant-response-event) 事件，以及已完成之 subagent 的 [`subagent_completed`](#subagent-completed-event)。在主工作階段與[同程序隊員](https://code.claude.com/docs/zh-TW/agent-teams.md#choose-a-display-mode)的事件上不存在。subagent 的 [span `agent_id`](#span-attributes) 是相同的值，或是在開頭的 `a` 後面加上標籤，如 `acompact-3f2c1b4d5e6f7a80`。需要 Claude Code v2.1.310 或更新版本
* `parent_agent_id`：產生或最後一次恢復引發事件之 subagent 的 agent 的 `agent_id`。當該 agent 為主工作階段時不存在。需要 Claude Code v2.1.310 或更新版本

#### 儲存庫屬性

設定 `OTEL_METRICS_INCLUDE_REPOSITORY=true`，即可在指標與事件上標記工作階段儲存庫的識別資訊，讓共用的收集器能依儲存庫歸屬用量。需要 Claude Code v2.1.269 或更新版本。

Claude Code 會在每個工作階段中從儲存庫的 `origin` remote 衍生這些屬性一次。當儲存庫的 HTTPS 與 SSH remote 指向相同主機與相同路徑時（如 GitHub、GitLab 與 Bitbucket Cloud），兩者會產生相同的值：

| 屬性 | 值 |
| - | - |
| `vcs.repository.url.full` | 儲存庫的瀏覽器 URL，不含 `.git`，例如 `https://github.com/example-org/example-repo` |
| `vcs.owner.name` | 擁有者或群組路徑，例如 `example-org`；當 remote 路徑只有單一區段時省略 |
| `vcs.repository.name` | 單純的儲存庫名稱，例如 `example-repo` |
| `vcs.provider.name` | 當 Claude Code 將 remote 的主機或 URL 形式識別為下列提供者之一時，為 `github`、`gitlab`、`bitbucket` 或 `gitea`；否則省略 |

值會轉為小寫，且 remote URL 中的憑證、查詢字串與片段絕不會出現在其中。當工作階段沒有 `origin` remote、remote 不是 URL 形式，或唯一的上層儲存庫是您的家目錄時，這些屬性會被省略。

若要從[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)取得這些屬性，請在其[雲端環境](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-environment-variables)上設定遙測變數，包括 `OTEL_METRICS_INCLUDE_REPOSITORY`。另外也要在環境的[網路存取](https://code.claude.com/docs/zh-TW/cloud-environments.md#network-access)中允許您收集器的網域。

您在 [`OTEL_RESOURCE_ATTRIBUTES`](#multi-team-organization-support) 中宣告的 `vcs.*` 鍵會取代該鍵的衍生值。如果您宣告了 `vcs.repository.url.full`，Claude Code 就完全不會讀取 remote，只回報您宣告的鍵。

如果同一儲存庫的 HTTPS 與 SSH clone 回報不同的值，例如在自行架設的安裝中，HTTPS clone URL 帶有 SSH URL 所沒有的路徑前綴，請在 `OTEL_RESOURCE_ATTRIBUTES` 中宣告 `vcs.repository.url.full`，以及您想回報的所有其他 `vcs.*` 鍵。如此一來，每個 clone 都會回報您宣告的識別資訊。

這些屬性只會流向您自己的匯出器；Anthropic 的遙測會捨棄所有 `vcs.*` 鍵。

### 指標

Claude Code 會匯出以下指標。「單位」欄顯示附加在每個指標上的 OpenTelemetry 單位字串；計數指標不帶單位。

| 指標名稱 | 說明 | 單位 |
| - | - | - |
| `claude_code.session.count` | 已啟動的 CLI 工作階段數量 | 無 |
| `claude_code.lines_of_code.count` | 已修改的程式碼行數 | 無 |
| `claude_code.pull_request.count` | 已建立的 pull request 數量 | 無 |
| `claude_code.commit.count` | 已建立的 git 提交數量 | 無 |
| `claude_code.cost.usage` | Claude Code 工作階段的費用 | USD |
| `claude_code.token.usage` | 使用的 token 數量 | tokens |
| `claude_code.code_edit_tool.decision` | 程式碼編輯工具權限決策的數量 | 無 |
| `claude_code.active_time.total` | 總活躍時間 | s |

當 `prometheus` 是 `OTEL_METRICS_EXPORTER` 中列出的唯一匯出器時，Claude Code 會從匯出的指標中省略 `USD`、`tokens` 與 `s` 單位，讓抓取結果保持有效的 Prometheus 文字格式。指標名稱不會改變，而組合多個匯出器的設定（例如 `otlp,prometheus`）則會保留單位。

### 指標詳細資訊

每個指標都包含上述的標準屬性。具有額外情境特定屬性的指標說明如下。

#### 工作階段計數器

在每個工作階段開始時遞增。

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `start_type`：工作階段的啟動方式。為 `"fresh"`、`"resume"`、`"continue"` 或 `"agents_view"` 之一。`"agents_view"` 值代表 `claude agents` 儀表板程序，這是由使用者啟動的本機 UI，而非對話式工作階段。在儀表板中篩選此值，即可將 UI 程序啟動與對話式工作階段區分開來。

#### 程式碼行數計數器

在新增或移除程式碼時遞增。

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `type`：（`"added"`、`"removed"`）
* `model`：進行變更之模型的模型識別碼（例如 "claude-sonnet-5"）

#### Pull request 計數器

在 Claude Code 透過 shell 命令或 MCP 工具建立 pull request 或 merge request 時遞增。

**屬性**：

* 所有[標準屬性](#standard-attributes)

#### 提交計數器

在透過 Claude Code 建立 git 提交時遞增。

**屬性**：

* 所有[標準屬性](#standard-attributes)

#### 費用計數器

在每次 API 請求後遞增。

`agent.name`、`skill.name`、`plugin.name`、`mcp_server.name` 與 `mcp_tool.name` 屬性預設都會將部分名稱遮蔽為 `"custom"` 或 `"third-party"` 預留值。如果您設定 `OTEL_LOG_TOOL_DETAILS=1`，它們就會改為攜帶真實名稱。在 v2.1.273 之前，即使設定了 `OTEL_LOG_TOOL_DETAILS=1`，費用與 token 計數器以及 `api_request`、`api_error` 與 `api_refusal` 事件仍會攜帶遮蔽後的值。

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `model`：模型識別碼（例如 "claude-sonnet-5"）
* `query_source`：發出請求之子系統的類別。為 `"main"`、`"subagent"` 或 `"auxiliary"` 之一
* `speed`：請求使用快速模式時為 `"fast"`。否則不存在
* `effort`：套用於請求的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)：`"low"`、`"medium"`、`"high"`、`"xhigh"` 或 `"max"`。當 Claude Code 未傳送 effort 等級時不存在，例如在不支援 effort 的模型上。
* `agent.name`：發出請求的 subagent 類型。內建 agent 名稱與來自官方市集外掛的 agent 會原樣顯示。其他使用者定義的 agent 名稱會被替換為 `"custom"`。當請求並非由具名的 subagent 類型發出時不存在。
* `skill.name`：請求當下啟用的 skill，由 Skill 工具或 `/` 命令設定，或由產生的 subagent 繼承。內建、隨附、使用者定義以及官方市集外掛的 skill 名稱會原樣顯示。第三方外掛的 skill 名稱會被替換為 `"third-party"`。沒有啟用的 skill 時不存在。
* `plugin.name`：當啟用的 skill 或 subagent 由外掛提供時，為所屬的外掛。官方市集外掛名稱會原樣顯示。第三方外掛名稱會被替換為 `"third-party"`。當 skill 與 subagent 都沒有所屬外掛時不存在。
* `marketplace.name`：所屬外掛的安裝來源市集。即使設定了 `OTEL_LOG_TOOL_DETAILS=1`，也只會針對官方市集外掛發出。否則不存在。
* `mcp_server.name`：此請求所使用之工具結果的 MCP 伺服器。內建、claude.ai 代理以及官方登錄中的伺服器名稱會原樣顯示。使用者設定的伺服器名稱會被替換為 `"custom"`。當請求未使用任何 MCP 工具結果時不存在。在 v2.1.222 之前，Claude Code 會在 MCP 工具呼叫之後的每個請求上設定此屬性，而不只是在使用了工具結果的請求上，因此彙總此屬性的儀表板在您升級後會出現下降。
* `mcp_tool.name`：此請求所使用之結果的 MCP 工具，遮蔽與版本行為與 `mcp_server.name` 相同。當請求未使用任何 MCP 工具結果時不存在。

#### Token 計數器

在每次 API 請求後遞增。

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `type`：（`"input"`、`"output"`、`"cacheRead"`、`"cacheCreation"`）。`"input"` 類型不包含從提示快取讀取或寫入的 token，這些 token 會計入 `"cacheRead"` 與 `"cacheCreation"`。`"cacheCreation"` 類型會將五分鐘與一小時[快取存留時間](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime)的快取寫入合併計算。
* `model`：模型識別碼（例如 "claude-sonnet-5"）
* `query_source`：發出請求之子系統的類別。為 `"main"`、`"subagent"` 或 `"auxiliary"` 之一
* `speed`：請求使用快速模式時為 `"fast"`。否則不存在
* `effort`：套用於請求的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)。詳細資訊請參閱[費用計數器](#cost-counter)。
* `agent.name`、`skill.name`、`plugin.name`、`marketplace.name`、`mcp_server.name`、`mcp_tool.name`：請求的 skill、外掛、agent 與 MCP 歸屬。定義與遮蔽行為請參閱[費用計數器](#cost-counter)。

#### 程式碼編輯工具決策計數器

在使用者接受或拒絕 Edit、Write 或 NotebookEdit 工具的使用時遞增。

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `tool_name`：工具名稱（`"Edit"`、`"Write"`、`"NotebookEdit"`）
* `decision`：使用者決策（`"accept"`、`"reject"`）
* `source`：決策的來源。為 `"config"`、`"hook"`、`"user_permanent"`、`"user_temporary"`、`"user_abort"` 或 `"user_reject"` 之一。各值的意義請參閱[工具決策事件](#tool-decision-event)。
* `language`：所編輯檔案的程式語言，例如 `"TypeScript"`、`"Python"`、`"JavaScript"` 或 `"Markdown"`。對於無法識別的副檔名會回傳 `"unknown"`。

#### 活躍時間計數器

追蹤實際主動使用 Claude Code 的時間，不含閒置時間。此指標會在使用者互動期間（例如輸入與閱讀回應）以及 CLI 處理期間（例如工具執行與 AI 回應產生）遞增。

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `type`：鍵盤互動為 `"user"`，工具執行與 AI 回應為 `"cli"`

### 事件

Claude Code 會透過 OpenTelemetry logs/events 匯出以下事件（當設定了 `OTEL_LOGS_EXPORTER` 時）：

#### 事件關聯屬性

當使用者送出提示詞時，Claude Code 可能會進行多次 API 呼叫並執行數個工具。`prompt.id` 屬性可讓您將所有這些事件連結回觸發它們的單一提示詞。

| 屬性 | 說明 |
| - | - |
| `prompt.id` | UUID v4 識別碼，連結處理單一使用者提示詞時產生的所有事件 |
| `event.sequence` | 用於排序事件的從 0 起算計數器，依每個 Claude Code 程序計算，而非依每個工作階段 |
| `message.uuid` | 保存在工作階段逐字稿（`~/.claude/projects/*/*.jsonl` 檔案）中之訊息的 UUID。出現在 `assistant_response`、`api_response_body` 上，以及 `user_prompt` 上（命令分派除外，因為命令分派可能產生零則或多則訊息）。在 `assistant_response` 與 `api_response_body` 上，這是回應的最後一筆逐字稿項目，下一個回合的 `parentUuid` 會由此串接。在 `api_response_body` 上需要 Claude Code v2.1.274 或更新版本 |
| `request_id` | 伺服器指派給 API 請求的 ID，從 `request-id` 回應標頭讀取，例如 `req_011...`。若回應沒有 `request-id` 標頭（如在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 上），則改從 `x-amzn-requestid` 標頭取得值。當回應攜帶任一標頭時，出現在 `api_request`、`api_error`、`api_refusal`、`assistant_response`、`api_response_body`、[`tool_result`](#tool-result-event) 與 [`tool_decision`](#tool-decision-event) 上。與 `llm_request` trace span 上的同名屬性相符。`x-amzn-requestid` 來源需要 Claude Code v2.1.282 或更新版本 |
| `client_request_id` | 用戶端產生的 UUID，以 `x-client-request-id` 請求標頭傳送。在第一方 API 連線上出現在 `api_request` 與 `api_error` 上；在第三方提供者後端，以及請求透過非串流備援重試時不存在。用於將請求與其回應配對，且對於從未產生伺服器 `request_id` 的失敗（例如逾時）仍可使用。與 `llm_request` trace span 上的同名屬性相符 |

若要追蹤由單一提示詞觸發的所有活動，請依特定的 `prompt.id` 值篩選事件。這會回傳處理該提示詞期間發生的 user\_prompt 事件、所有 api\_request 事件，以及所有 tool\_result 事件。

`event.sequence` 在每次 Claude Code 程序啟動時從 0 開始，並在該程序的存續期間持續遞增。它在 `/clear`（會指派新的 `session.id`）之後仍會繼續計數。如果您[在不分支的情況下恢復工作階段](https://code.claude.com/docs/zh-TW/how-claude-code-works.md#resume-or-fork-sessions)，工作階段會保留其 `session.id`，但 `event.sequence` 值會取自恢復它的程序，因此在同一個工作階段內，較晚的事件可能攜帶比較早事件更低的值，或重複某個值。若要排序工作階段的事件，請依 `event.timestamp` 排序，並使用 `event.sequence` 排序時間戳記相同的事件。

若要進行訊息層級的重建，每個事件類別都帶有一個與工作階段逐字稿中某欄位相符的鍵。逐字稿項目格式是 [Claude Code 內部使用的](https://code.claude.com/docs/zh-TW/sessions.md#where-transcripts-are-stored)，且會隨版本變動，因此依這些欄位進行聯結的管線可能在任何版本發布時中斷；請將這些聯結視為特定版本適用，而非穩定的約定：

* `user_prompt`、`assistant_response` 與 `api_response_body` 上的 `message.uuid`
* API 事件上的 `request_id`，在逐字稿的 assistant 項目上保存為 `requestId`
* `tool_result` 與 `tool_decision` 事件上的 `tool_use_id`，以及 `safety_event` 事件上的 `tool_use_id`（[回合結束](#safety-event)的事件除外）

#### 使用者提示詞事件

在送出提示詞時記錄，包括 Claude Code 自行開始的回合。

**事件名稱**：`claude_code.user_prompt`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"user_prompt"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `prompt_length`：提示詞的長度
* `prompt`：提示詞內容。預設會遮蔽。設定 `OTEL_LOG_USER_PROMPTS=1` 即可包含
* `prompt_text`：與 `prompt` 相同的值，受相同條件遮蔽。將帶點號的屬性名稱儲存為巢狀物件的後端，會將 `prompt.id` 讀取為名為 `prompt` 之物件內的 `id`，因而可能遺失提示詞字串。在這類後端中請改讀取 `prompt_text`。需要 Claude Code v2.1.287 或更新版本
* `message.uuid`：產生的使用者訊息的 UUID，與保存的逐字稿項目相符。在命令分派上不存在，因為命令分派可能產生零則或多則訊息。
* `command_name`：提示詞呼叫命令時的命令名稱。內建與隨附的命令名稱（例如 `compact` 或 `debug`）會原樣發出；別名（例如 `reset`）會依輸入內容發出，而非標準名稱。自訂、外掛與 MCP 命令名稱會收斂為 `custom` 或 `mcp`，除非設定了 `OTEL_LOG_TOOL_DETAILS=1`
* `command_source`：存在命令時的命令來源：`builtin`、`custom` 或 `mcp`。由外掛提供的命令會回報為 `custom`

#### Assistant 回應事件

在每次從模型傳回文字內容的 API 請求後記錄。只包含回應的文字區塊；思考區塊與工具使用區塊不包含在內。

**事件名稱**：`claude_code.assistant_response`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"assistant_response"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `response_length`：回應文字的長度（以字元計）
* `response`：回應文字，在內容上限處截斷（預設 60 KB）。預設會遮蔽為 `<REDACTED>`。設定 `OTEL_LOG_ASSISTANT_RESPONSES=1` 即可包含。當未設定 `OTEL_LOG_ASSISTANT_RESPONSES` 時，改由 `OTEL_LOG_USER_PROMPTS` 控制，因此若要在開啟提示詞記錄的同時保持回應遮蔽，請設定 `OTEL_LOG_ASSISTANT_RESPONSES=0`
* `model`：模型識別碼（例如 "claude-sonnet-5"）
* `request_id`：API 請求 ID，說明請見[事件關聯屬性](#event-correlation-attributes)
* `message.uuid`：回應最後一筆逐字稿項目的 UUID。API 回應會以每個內容區塊一筆逐字稿項目的方式保存；這是最後一筆，下一個回合的 `parentUuid` 會由此串接。
* `query_source`：發出請求的子系統，例如 `"repl_main_thread"`、`"compact"` 或 subagent 名稱

#### 工具結果事件

在工具完成執行時記錄。若工具呼叫遭拒絕則不會發出；關於拒絕，請參閱[工具決策事件](#tool-decision-event)。

**事件名稱**：`claude_code.tool_result`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"tool_result"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `tool_name`：工具名稱
* `tool_use_id`：此工具呼叫的唯一識別碼。與傳遞給 hook 的 `tool_use_id` 相符，可讓 OTel 事件與 hook 擷取的資料相互關聯。
* `request_id`：包含此工具呼叫之 API 回應的 [`request_id`](#event-correlation-attributes)，讓您可以將此呼叫與該回應的 API 事件聯結。當該回應沒有請求 ID，或沒有任何 API 回應包含此呼叫時不存在。需要 Claude Code v2.1.310 或更新版本
* `success`：`"true"` 或 `"false"`
* `duration_ms`：執行時間（毫秒）
* `error_type`：工具失敗時的錯誤類別字串，例如 `"Error:ENOENT"` 或 `"ShellError"`
* `error`（當 `OTEL_LOG_TOOL_DETAILS=1` 時）：工具失敗時的完整錯誤訊息
* `decision_type`：一律為 `"accept"`，因為此事件只會在工具執行後發出。遭拒絕的呼叫不會產生工具結果
* `decision_source`：權限決策的來源。為 `"config"`、`"hook"`、`"user_permanent"` 或 `"user_temporary"` 之一。各值的意義請參閱[工具決策事件](#tool-decision-event)。僅用於拒絕的來源 `"user_abort"` 與 `"user_reject"` 絕不會出現在此事件上。
* `tool_input_size_bytes`：JSON 序列化後工具輸入的大小（位元組）
* `tool_result_size_bytes`：工具結果的大小（位元組）
* `mcp_server_scope`：MCP 伺服器範圍識別碼（適用於 MCP 工具）
* `vcs.ref.head.revision`、`vcs.ref.head.name`、`vcs.ref.head.type`（當 `OTEL_LOG_TOOL_DETAILS=1` 時）：由 Bash 或 PowerShell 工具執行之成功 `git commit` 的提交識別資訊。`vcs.ref.head.revision` 是提交 SHA，`vcs.ref.head.name` 是提交所在的分支，而 `vcs.ref.head.type` 為 `branch`。當提交是在 detached HEAD 上進行時，會省略名稱與類型。需要 Claude Code v2.1.269 或更新版本
* `tool_parameters`（當 `OTEL_LOG_TOOL_DETAILS=1` 時）：包含工具特定參數的 JSON 字串。對於 Claude Desktop 的內建伺服器，在 Claude Desktop 擁有的工作階段中，即使旗標關閉也會包含 `mcp_server_name`/`mcp_tool_name` 組合，這與[工具決策事件](#tool-decision-event)的主機定義例外相同。參數因工具而異：
  * 對於 Bash 工具：包含 `bash_command`、`full_command`、`timeout`、`description` 與 `dangerouslyDisableSandbox`，以及 `git commit` 命令成功時的 `git_commit_id` 與 `git_branch`。當提交是工作階段工作目錄的 HEAD 時，`git_commit_id` 是完整的提交 SHA，否則是 git 的縮寫 SHA。`git_branch` 是提交所在的分支，在 detached HEAD 上會省略
  * 對於桌面應用程式的工作區 Bash 工具（同樣將 `tool_name` 回報為 `Bash`）：只包含 `bash_command`、`full_command` 與 `timeout`
  * 對於 MCP 工具：包含 `mcp_server_name`、`mcp_tool_name`
  * 對於 Skill 工具：包含 `skill_name`
  * 對於 Agent 工具或舊版 Task 工具：包含 `subagent_type`
* `tool_input`（當 `OTEL_LOG_TOOL_DETAILS=1` 時）：JSON 序列化的工具引數。超過 512 個字元的個別值會被截斷，而完整 payload 的上限約為 4 K 個字元。適用於所有工具，包括 MCP 工具。

#### API 請求事件

針對每個傳送給 Claude 的 API 請求記錄。

**事件名稱**：`claude_code.api_request`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"api_request"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `model`：使用的模型（例如 "claude-sonnet-5"）
* `cost_usd`：估計費用（美元）
* `cost_usd_micros`：估計費用，以百萬分之一美元為單位，以整數發出
* `duration_ms`：請求持續時間（毫秒）
* `input_tokens`：輸入 token 數量，不含從提示快取讀取或寫入的 token
* `output_tokens`：輸出 token 數量
* `cache_read_tokens`：從快取讀取的 token 數量
* `cache_creation_tokens`：用於建立快取的 token 數量
* `cache_creation_5m_tokens`、`cache_creation_1h_tokens`：API 回應所回報、以五分鐘[快取存留期](https://code.claude.com/docs/zh-TW/prompt-caching.md#cache-lifetime)寫入快取的 token 數量，以及以一小時存留期寫入的數量。當 API 回應未回報這些值時，兩者皆為 `0`，即使 `cache_creation_tokens` 大於零亦然。需要 Claude Code v2.1.300 或更新版本
* `request_id`：API 請求 ID，例如 `"req_011..."`，說明請見[事件關聯屬性](#event-correlation-attributes)。
* `client_request_id`：用戶端產生的 UUID，以 `x-client-request-id` 請求標頭傳送；何時存在請參閱[事件關聯屬性](#event-correlation-attributes)表格
* `speed`：`"fast"` 或 `"normal"`，表示快速模式是否啟用
* `query_source`：發出請求的子系統，例如 `"repl_main_thread"`、`"compact"` 或 subagent 名稱
* `effort`：套用於請求的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)：`"low"`、`"medium"`、`"high"`、`"xhigh"` 或 `"max"`。當 Claude Code 未傳送 effort 等級時不存在，例如在不支援 effort 的模型上。
* `agent.name`、`skill.name`、`plugin.name`、`marketplace.name`、`mcp_server.name`、`mcp_tool.name`：請求的 skill、外掛、agent 與 MCP 歸屬。定義與遮蔽行為請參閱[費用計數器](#cost-counter)。

#### API 錯誤事件

在傳送給 Claude 的 API 請求失敗時記錄。

**事件名稱**：`claude_code.api_error`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"api_error"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `model`：使用的模型（例如 "claude-sonnet-5"）
* `error`：錯誤訊息
* `status_code`：HTTP 狀態碼（數字）。對於非 HTTP 錯誤（例如連線失敗）不存在。
* `duration_ms`：請求持續時間（毫秒）
* `attempt`：嘗試次數，包含初始請求。計數何時重新開始，請參閱[偵測重試耗盡](#detect-retry-exhaustion)
* `request_id`：API 請求 ID，例如 `"req_011..."`，說明請見[事件關聯屬性](#event-correlation-attributes)。
* `client_request_id`：用戶端產生的 UUID，以 `x-client-request-id` 請求標頭傳送。即使逾時或連線錯誤等失敗從未產生伺服器 `request_id` 時仍可使用；何時存在請參閱[事件關聯屬性](#event-correlation-attributes)表格。
* `speed`：`"fast"` 或 `"normal"`，表示快速模式是否啟用
* `query_source`：發出請求的子系統，例如 `"repl_main_thread"`、`"compact"` 或 subagent 名稱
* `effort`：套用於請求的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)。當 Claude Code 未傳送 effort 等級時不存在，例如在不支援 effort 的模型上。
* `agent.name`、`skill.name`、`plugin.name`、`marketplace.name`、`mcp_server.name`、`mcp_tool.name`：請求的 skill、外掛、agent 與 MCP 歸屬。定義與遮蔽行為請參閱[費用計數器](#cost-counter)。

#### API 拒絕事件

在 API 請求傳回 `stop_reason: "refusal"` 時記錄。拒絕是在成功的回應串流中傳回，而非以 HTTP 錯誤形式傳回，因此 `api_error` 事件不會因拒絕而觸發。此事件可讓您追蹤拒絕頻率，並依照與 `api_request` 和 `api_error` 相同的屬性將拒絕分組。

**事件名稱**：`claude_code.api_refusal`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"api_refusal"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `model`：請求中的模型識別碼
* `request_id`：API 請求 ID，例如 `"req_011..."`，說明請見[事件關聯屬性](#event-correlation-attributes)。
* `query_source`：發出請求的子系統，例如 `"repl_main_thread"`、`"compact"` 或 subagent 名稱。定義請參閱 [`api_request`](#api-request-event)。
* `speed`：當[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)啟用時為 `"fast"`，否則為 `"normal"`
* `attempt`：重試嘗試編號。第一次嘗試為 `1`。
* `effort`：套用於請求的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)。當 Claude Code 未傳送 effort 等級時不存在，例如在不支援 effort 的模型上。
* `server_fallback_hop`：當 API 的伺服器端模型備援已在不同模型上重試此拒絕，因此使用者並未看到這次特定的拒絕時為 `true`。當請求以拒絕結束時為 `false`。當備援模型也拒絕時，單一回合可能會同時發出一個 `true` 的跳轉事件與之後一個 `false` 的最終事件。
* `has_category`：當 API 回應攜帶的 `stop_details.category` 為 `"cyber"`、`"bio"`、`"frontier_llm"` 或 `"reasoning_extraction"` 時為 `true`。當回應未攜帶類別或值不在該集合中時為 `false`。當 `server_fallback_hop` 為 `true` 時不存在，因為跳轉區塊不攜帶 `stop_details`。
* `has_explanation`：當 API 回應攜帶 `stop_details.explanation` 時為 `true`，否則為 `false`。當 `server_fallback_hop` 為 `true` 時不存在。
* `category`：API 回應中的 `stop_details.category` 值。為 `"cyber"`、`"bio"`、`"frontier_llm"` 或 `"reasoning_extraction"` 之一。只有在設定了 `OTEL_LOG_TOOL_DETAILS=1` 且 `has_category` 為 `true` 時才存在。
* `agent.name`、`skill.name`、`plugin.name`、`marketplace.name`、`mcp_server.name`、`mcp_tool.name`：請求的 skill、外掛、agent 與 MCP 歸屬。定義與遮蔽行為請參閱[費用計數器](#cost-counter)。

#### API 請求主體事件

當設定了 `OTEL_LOG_RAW_API_BODIES` 時，針對每次 API 請求嘗試記錄。每次嘗試發出一個事件，因此以調整後參數進行的重試都會各自產生自己的事件。

**事件名稱**：`claude_code.api_request_body`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"api_request_body"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `body`：JSON 序列化的 Messages API 請求參數，例如系統提示詞、訊息與工具，在內容上限處截斷（預設 60 KB）。先前 assistant 回合中的延伸思考內容會被遮蔽。僅在內嵌模式（`OTEL_LOG_RAW_API_BODIES=1`）下發出。
* `body_ref`：包含未截斷主體之 `<dir>/<uuid>.request.json` 檔案的絕對路徑。僅在檔案模式（`OTEL_LOG_RAW_API_BODIES=file:<dir>`）下發出。
* `body_length`：未截斷的主體長度。當 `OTEL_LOG_RAW_API_BODIES=file:<dir>` 時為 UTF-8 位元組數，當 `=1` 時為 UTF-16 碼元數
* `body_truncated`：發生內嵌截斷時為 `"true"`。在檔案模式下以及未發生截斷時不存在。
* `model`：請求參數中的模型識別碼
* `query_source`：發出請求的子系統（例如 `"compact"`）
* `request_body_id`：識別此次嘗試之請求主體的 UUID。成功之嘗試的 [`api_response_body` 事件](#api-response-body-event)會攜帶相同的值，因此您可以將回應與產生它的確切請求配對。需要 Claude Code v2.1.274 或更新版本

#### API 回應主體事件

當設定了 `OTEL_LOG_RAW_API_BODIES` 時，針對每個成功的 API 回應記錄。

在檔案模式（`OTEL_LOG_RAW_API_BODIES=file:<dir>`）下，Claude Code 也會針對每個成功的回應，在 `<dir>/index.jsonl` 中附加一行 JSON，包含欄位 `timestamp`、`session_id`、`query_source`、`model`、`request_id`、`message_id`、`message_uuid`、`request_file` 與 `response_file`。讀取此檔案即可找出特定逐字稿訊息背後的請求與回應檔案，而不需查詢您的遙測後端。索引檔需要 Claude Code v2.1.274 或更新版本。

**事件名稱**：`claude_code.api_response_body`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"api_response_body"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `body`：JSON 序列化的 Messages API 回應，包括 id、內容區塊、用量與停止原因，在內容上限處截斷（預設 60 KB）。延伸思考內容會被遮蔽。僅在內嵌模式（`OTEL_LOG_RAW_API_BODIES=1`）下發出。
* `body_ref`：包含未截斷主體之 `<dir>/<request_id>.response.json` 檔案的絕對路徑。僅在檔案模式（`OTEL_LOG_RAW_API_BODIES=file:<dir>`）下發出。
* `body_length`：未截斷的主體長度。當 `OTEL_LOG_RAW_API_BODIES=file:<dir>` 時為 UTF-8 位元組數，當 `=1` 時為 UTF-16 碼元數
* `body_truncated`：發生內嵌截斷時為 `"true"`。在檔案模式下以及未發生截斷時不存在。
* `model`：模型識別碼
* `query_source`：發出請求的子系統
* `request_id`：API 請求 ID，例如 `"req_011..."`，說明請見[事件關聯屬性](#event-correlation-attributes)。
* `request_body_id`：此回應所對應之 [`api_request_body` 事件](#api-request-body-event)的 `request_body_id`。需要 Claude Code v2.1.274 或更新版本
* `message.id`：API 指派給回應的訊息 ID，即回應主體的 `id` 欄位。需要 Claude Code v2.1.274 或更新版本
* `message.uuid`：回應最後一筆逐字稿項目的 UUID。搭配 `request_body_id`，可將逐字稿訊息連結到其背後的請求與回應主體。需要 Claude Code v2.1.274 或更新版本

#### 工具決策事件

在做出工具權限決策（接受/拒絕）時記錄。

**事件名稱**：`claude_code.tool_decision`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"tool_decision"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `tool_name`：工具名稱（例如 "Read"、"Edit"、"Write"、"NotebookEdit"）
* `tool_use_id`：此工具呼叫的唯一識別碼。與傳遞給 hook 的 `tool_use_id` 相符，可讓 OTel 事件與 hook 擷取的資料相互關聯。
* `request_id`：包含此工具呼叫之 API 回應的 [`request_id`](#event-correlation-attributes)，讓您可以將此呼叫與該回應的 API 事件聯結。當該回應沒有請求 ID，或沒有任何 API 回應包含此呼叫時不存在。需要 Claude Code v2.1.310 或更新版本
* `decision`：`"accept"` 或 `"reject"`
* `tool_source`：一律存在。工具的來源，為 CLI 定義的封閉值集合：
  * `"builtin"`：CLI 自身的工具
  * `"mcp"`：一般的 MCP 伺服器
  * `"sdk_host_builtin_mcp"`：內建於 Claude Desktop 本身的同程序伺服器，位於 Claude Desktop 擁有的工作階段中。當工作階段是 Claude Desktop 從其自身進入點（`claude-desktop`、`claude-desktop-3p` 或 `local-agent`）啟動，且該工作階段不是巢狀子工作階段時，Claude Desktop 即擁有該工作階段；巢狀工作階段（包括 Claude Code 本身產生的工作階段）會將這些伺服器回報為 `"mcp"`
* `source`：決策的來源：
  * `"config"`：未經提示即自動決定，由下列來源之一決定：

    * 專案設定
    * 使用者個人設定中的允許或拒絕規則
    * 企業受管政策
    * `--allowedTools` 或 `--disallowedTools` 旗標
    * 目前的權限模式
    * 自動模式分類器，其判定由同一事件記錄於 `classifier_verdict`
    * 在同一互動式 CLI 工作階段中，於較早的權限提示時授予的剩餘工作階段授權
    * 工具本身即屬安全

    `source` 值不會指出是哪一個來源相符。若要找出是哪一個來源拒絕了某次呼叫，請尋找具有相同 `tool_use_id` 的[安全事件](#safety-event)，並讀取其 `category` 與 `rule_source` 屬性。部分遭拒絕的呼叫[沒有安全事件](#calls-without-a-safety-event)。

    當權限提示請求本身失敗時，Claude Code 也會回報 `"config"`。例如，當 Agent SDK 的 [`canUseTool`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#canusetool) 回呼或 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 工具傳回無效結果，或在請求待處理期間輸入串流關閉時，該請求就會失敗。
  * `"hook"`：由 `PreToolUse` 或 `PermissionRequest` hook 傳回決策。
  * `"user_permanent"`：當使用者在權限提示中選擇「Yes, and don't ask again for ...」時發出，這會將允許規則儲存到其個人設定中。在互動式 CLI 中，只有該選擇本身會發出此值；之後符合已儲存規則的呼叫會改為發出 `"config"`。在 Agent SDK 或非互動式 `-p` 工作階段中，初次選擇與之後的規則相符都會發出 `"user_permanent"`。視為接受。
  * `"user_temporary"`：當使用者在權限提示中選擇「Yes」進行一次性核准，或在檔案編輯或讀取提示中選擇授予剩餘工作階段存取權的選項時發出。在互動式 CLI 中，只有該選擇本身會發出此值；之後由該工作階段範圍授權所允許的呼叫會改為發出 `"config"`。在 Agent SDK 或非互動式 `-p` 工作階段中，該選擇與之後的相符都會發出 `"user_temporary"`。視為接受。
  * `"user_abort"`：當使用者未作答即關閉權限提示時發出。在 Agent SDK 與非互動式 `-p` 工作階段中，這包括在 `canUseTool` 或 `--permission-prompt-tool` 權限請求待處理時中斷回合。視為拒絕。
  * `"user_reject"`：當使用者在提示時選擇「No」時發出。在互動式 CLI 中，只有該選擇本身會發出此值；符合使用者個人設定中拒絕規則的呼叫會改為發出 `"config"`。在 Agent SDK 或非互動式 `-p` 工作階段中，符合個人設定中拒絕規則的呼叫會發出 `"user_reject"`。視為拒絕。
* `classifier_verdict`：自動模式[分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#how-the-classifier-evaluates-actions)對該呼叫的判定，或在沒有判定時 Claude Code 拒絕該呼叫的原因。需要 Claude Code v2.1.301 或更新版本

  * `"allow"`：分類器核准了該呼叫
  * `"block"`：分類器封鎖了該呼叫。中途失敗的分類器檢查也可能以 `"block"` 結束，因此分類器部分中斷時可能表現為封鎖增加，而非 `"unavailable"`
  * `"no_verdict"`：檢查已執行但未給出[可用的判定](https://code.claude.com/docs/zh-TW/errors.md#auto-mode-cannot-determine-the-safety-of-an-action)，因此 Claude Code 拒絕了該呼叫。此拒絕並不代表分類器認為該呼叫不安全
  * `"unavailable"`：傳送給分類器的請求失敗，例如遇到速率限制、逾時或連線錯誤，因此 Claude Code 拒絕了該呼叫。在使用[伺服器端分類器審查](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)時，它也用於標示因[伺服器未傳回安全判定](https://code.claude.com/docs/zh-TW/errors.md#the-server-returned-no-safety-verdict)而遭拒絕的呼叫

  當[分類器在 plan mode 中審查命令](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode)時，此屬性也會出現在 plan mode 的呼叫上。在下列情況中此屬性不存在：

  * 由允許或拒絕的[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)決定該呼叫
  * Claude Code 在自動模式中未詢問分類器即核准了該呼叫
  * 使用者回答了 Claude Code 在[重複封鎖](https://code.claude.com/docs/zh-TW/permission-modes.md#repeated-block-thresholds)後顯示的提示
  * 在沒有 `--permission-prompt-tool` 的 `-p` 執行中，由於沒有人能回答提示，Claude Code 在重複封鎖後拒絕了該呼叫。該事件會將 `decision` 回報為 `"reject"`，並將 `source` 回報為 `"config"`
* `classifier_category`（當 `OTEL_LOG_TOOL_DETAILS=1` 時）：分類器封鎖該呼叫時所指名之[內建規則](https://code.claude.com/docs/zh-TW/auto-mode-config.md#inspect-the-defaults-and-your-effective-config)的名稱，以小寫加底線表示，例如 Data Exfiltration 規則的 `"data_exfiltration"`。需要 Claude Code v2.1.301 或更新版本。當下列兩項條件都成立時，此屬性才會存在：

  * `classifier_verdict` 為 `"block"`
  * 分類器恰好指名了一條規則，且該規則是內建規則，而非您撰寫的規則

  在 v2.1.302 之前，由[伺服器端分類器審查](https://code.claude.com/docs/zh-TW/permission-modes.md#server-side-classifier-review)決定的任何封鎖上也不存在此屬性。
* `permission_mode`：此呼叫的權限檢查開始時所使用的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)：`"default"`、`"plan"`、`"acceptEdits"`、`"bypassPermissions"`、`"dontAsk"` 或 `"auto"`。手動模式會顯示為 `"default"`。[subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#permission-modes) 的呼叫會回報 subagent 的權限模式，而非工作階段的權限模式。需要 Claude Code v2.1.301 或更新版本
* `tool_parameters`（當 `OTEL_LOG_TOOL_DETAILS=1` 時）：包含工具特定參數的 JSON 字串。形式與[工具結果事件](#tool-result-event)相同，但不含 `git_commit_id` 等執行後欄位。對於已接受的呼叫，若權限決策透過 `updatedInput` 改寫了工具輸入，值可能與 `tool_result` 不同。當 `decision` 為 `"reject"` 時，可使用此屬性查看哪個命令遭拒絕。
  * 對於 `"sdk_host_builtin_mcp"` 工具：即使 `OTEL_LOG_TOOL_DETAILS` 關閉，也會包含 `mcp_server_name` 與 `mcp_tool_name`，因為這些名稱是由主機應用程式定義的；若沒有它們，對這些內建伺服器之一的遭拒絕呼叫在預設串流中將無法歸屬。對於使用者設定的 MCP 伺服器，事件的 `tool_name` 一律是字面值 `"mcp_tool"`，而伺服器與工具名稱只會在旗標開啟時出現在 `tool_parameters` 中；引數內容在任何情況下都需要該旗標。
  * 對於 Bash 工具：包含 `bash_command`、`full_command`、`timeout`、`description`、`dangerouslyDisableSandbox`。桌面應用程式的工作區 bash 工具也會將 `tool_name` 回報為 `Bash`，但只包含 `bash_command`、`full_command` 與 `timeout`
  * 對於 MCP 工具：包含 `mcp_server_name`、`mcp_tool_name`
  * 對於 Skill 工具：包含 `skill_name`
  * 對於 Agent 工具或舊版 Task 工具：包含 `subagent_type`

如果您將 OpenTelemetry SDK 的 `OTEL_LOGRECORD_ATTRIBUTE_COUNT_LIMIT` 調低到少於 `tool_decision` 事件上的屬性數量，SDK 會捨棄 Claude Code 最後設定的屬性。SDK 會在其他任何屬性之前依下列順序捨棄這些屬性，並略過事件未攜帶的屬性：

1. `parent_agent_id`
2. `agent_id`
3. `request_id`
4. `permission_mode`
5. `classifier_category`
6. `classifier_verdict`

在 Claude Code v2.1.302 或更新版本上，`permission_mode`、`classifier_category` 與 `classifier_verdict` 會依此順序捨棄。`parent_agent_id`、`agent_id` 與 `request_id` 需要 v2.1.310 或更新版本。

#### 安全事件

在檢查拒絕工具呼叫或需要權限提示時記錄，[沒有安全事件的呼叫](#calls-without-a-safety-event)除外。當[沙箱的網路代理伺服器](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)拒絕連線或請求，以及 hook 封鎖結果時也會記錄。需要 Claude Code v2.1.307 或更新版本。

此事件會與其他事件一起匯出，沒有獨立的設定。事件本身的屬性不包含命令文字、檔案路徑、主機名稱，或 MCP 伺服器與工具名稱。該記錄也會攜帶每個事件都有的[標準屬性](#standard-attributes)，其中可能包括 `workspace.host_paths` 與[儲存庫屬性](#repository-attributes)。若要查看事件背後的命令或 MCP 工具，請設定 `OTEL_LOG_TOOL_DETAILS=1`，並讀取相符之 `tool_decision` 事件上的 `tool_parameters`。

**事件名稱**：`claude_code.safety_event`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"safety_event"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `category`：檢查或結果，為一個[類別值](#safety-event-categories)
* `decision`：`"accept"`、`"reject"`，或當 hook 封鎖結果或回合結束時為 `"sent_back"`
* `decision_source`：做出決定的主體或機制，為 [`tool_decision`](#tool-decision-event) 的 `source` 值或 `"other"`
* `reason_code`：檢查的原因，例如 `"rule:policySettings"`、`"mode:dontAsk"`、`"hook:PreToolUse"`、`"classifier:auto-mode"`、`"bashMiss:too-complex"` 或 `"unknown"`
* `reason_type`：檢查的原因類型，例如 `"rule"`、`"subcommandResults"`、`"mode"`、`"hook"`、`"classifier"` 或 `"asyncAgent"`
* `rule_source`：所涉規則的設定來源，例如 `"policySettings"`、`"userSettings"`、`"projectSettings"`、`"localSettings"`、`"flagSettings"`、`"cliArg"` 或 `"session"`
* `grant_scope`：對於未將規則儲存到設定檔即核准的提示，為 `"once"` 或 `"session"`
* `circuit_breaker`：內建的安全檢查，例如 `"dangerousRemoval"`、`"outsideReadsBlocked"` 或 `"claudeSettingsFile"`
* `classifier_category`：在 `OTEL_LOG_TOOL_DETAILS=1` 時，自動模式封鎖背後的[內建規則](https://code.claude.com/docs/zh-TW/auto-mode-config.md#inspect-the-defaults-and-your-effective-config)，例如 `"data_exfiltration"`
* `hook_event`：`PreToolUse` hook 為 `"pre_tool_use"`，或在 `"hook_review"` 事件上為 `"post_tool_use"`、`"post_tool_use_failure"`、`"stop"` 或 `"subagent_stop"`
* `tool_class`：Bash 與 [Monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool) 為 `"bash"`，`"powershell"`，Read、Edit、Write、NotebookEdit、Glob 與 Grep 為 `"file"`，WebFetch 與 WebSearch 為 `"web"`，`"mcp"`，或 `"other"`
* `tool_name`：工具名稱，例如內建工具的 `"Bash"`，或 `"mcp_tool"`、`"skill_tool"`、`"dynamic_tool"` 或 `"other_tool"`
* `tool_source`：`"builtin"`、`"mcp"` 或 `"sdk_host_builtin_mcp"`，與 [`tool_decision`](#tool-decision-event) 上相同
* `permission_mode`：檢查時該呼叫的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)：`"default"`、`"plan"`、`"acceptEdits"`、`"bypassPermissions"`、`"dontAsk"` 或 `"auto"`
* `tool_use_id`：呼叫的 ID，與 `tool_decision` 和 `tool_result` 上相同
* `sandbox_violation_count`：沙箱的網路代理伺服器拒絕了該呼叫之命令的多少個不同連線或請求，以字串表示，範圍為 `"0"` 到 `"20"`。僅計算在前景完成之沙箱化命令的拒絕
* `sandbox_enabled`：若工作階段啟用了[沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)則為 `"true"`，否則為 `"false"`

以下是受管設定的拒絕規則拒絕 Bash 命令時，事件本身的屬性：

```json theme={null}
{
  "event.name": "safety_event",
  "category": "managed_policy",
  "decision": "reject",
  "decision_source": "config",
  "reason_code": "rule:policySettings",
  "rule_source": "policySettings",
  "tool_class": "bash",
  "tool_name": "Bash",
  "tool_source": "builtin",
  "permission_mode": "default",
  "tool_use_id": "toolu_01ABC123...",
  "sandbox_violation_count": "0",
  "sandbox_enabled": "false"
}
```

##### 安全事件類別

| 值 | 檢查或結果 | 詳細資訊屬性 |
| - | - | - |
| `"permission_rule"` | 受管設定以外的拒絕或詢問[權限規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions) | `rule_source` |
| `"managed_policy"` | 來自[受管設定](https://code.claude.com/docs/zh-TW/permissions.md#managed-settings)的拒絕或詢問規則 | `rule_source` |
| `"permission_mode"` | [`dontAsk`](https://code.claude.com/docs/zh-TW/permission-modes#allow-only-pre-approved-tools-with-dontask-mode) 或 [plan](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 模式，或在無法顯示提示的工作階段中（例如使用 [`--permission-prompts none`](https://code.claude.com/docs/zh-TW/headless#turn-off-permission-prompts-in-unattended-runs) 時）出現的[無類別](#prompts-with-no-category)提示 | `reason_code`、`reason_type` |
| `"hook"` | hook，例如 [`PreToolUse`](https://code.claude.com/docs/zh-TW/hooks#pretooluse) 或 [`PermissionRequest`](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) | `hook_event`、`reason_code` |
| `"auto_mode_block"` | 自動模式[分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#how-the-classifier-evaluates-actions)封鎖了該呼叫 | `classifier_category` |
| `"auto_mode_no_verdict"` | 沒有可用的[分類器判定](https://code.claude.com/docs/zh-TW/errors.md#auto-mode-cannot-determine-the-safety-of-an-action)，例如在請求失敗之後 | `reason_code` |
| `"safety_check"` | 內建的安全檢查，例如針對在您的[工作目錄](https://code.claude.com/docs/zh-TW/permissions.md#working-directories)以外進行的 Read、Edit 或 Write | `circuit_breaker` |
| `"static_analysis"` | Bash 或 Monitor 命令的撰寫方式，例如過於複雜而無法分析的命令 | `reason_code` |
| `"sandbox_override"` | [在沙箱外執行命令](https://code.claude.com/docs/zh-TW/sandboxing.md#the-unsandboxed-retry-escape-hatch)的提示 | `reason_code` |
| `"user_rejected"` | 有人拒絕或關閉了[無類別](#prompts-with-no-category)或僅由 hook 要求的提示，或 `canUseTool` 回呼或 `--permission-prompt-tool` 工具拒絕了這類提示 | `decision_source` |
| `"sandbox_network"` | 呼叫已執行，且[沙箱的網路代理伺服器](https://code.claude.com/docs/zh-TW/sandboxing.md#network-isolation)拒絕了連線或請求 | `sandbox_violation_count` |
| `"sandbox_other"` | 與 `"sandbox_network"` 類似，但沒有任何遭拒絕的目標可解讀為主機名稱或 IP 位址 | `sandbox_violation_count` |
| `"hook_review"` | hook [封鎖了呼叫的結果](https://code.claude.com/docs/zh-TW/hooks.md#posttooluse-decision-control)或[回合的結束](https://code.claude.com/docs/zh-TW/hooks.md#stop-decision-control) | `hook_event` |
| `"other"` | 其他值皆無法描述的拒絕 | `reason_code` |

若要找出任何 `category` 下的代理伺服器拒絕，請篩選存在且不為 `"0"` 的 `sandbox_violation_count`。

##### 沒有安全事件的呼叫

若要找出因無人能回答[無類別提示](#prompts-with-no-category)而遭拒絕的呼叫，請尋找回報 `"reject"`、`source` 為 `"config"`，且沒有安全事件共用其 `tool_use_id` 的 [`tool_decision`](#tool-decision-event) 事件。這類拒絕發生在既沒有 [`--permission-prompt-tool`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 也沒有 `--permission-prompts none` 的 `-p` 執行中。

對於下列這類呼叫，請檢查其 `tool_decision` 事件，因為除了在執行後發送的 [`"sandbox_network"`、`"sandbox_other"` 或 `"hook_review"` 事件](#safety-event-categories)之外，它們沒有安全事件：

* 在無類別提示中獲得核准的呼叫
* 在僅由 `PreToolUse` hook 要求的提示中，由 `canUseTool` 回呼或 `--permission-prompt-tool` 工具核准的呼叫
* [`AskUserQuestion`](https://code.claude.com/docs/zh-TW/tools-reference#askuserquestion-tool-behavior) 或 `ExitPlanMode` 呼叫，無論是否遭拒絕

##### 無類別的提示

當沒有任何 [`category` 值](#safety-event-categories)指名某個提示的檢查時，該提示即為無類別，例如針對工作目錄內編輯的 `default` 模式提示。

#### 權限模式變更事件

在權限模式變更時記錄，例如透過 `Shift+Tab` 循環切換、退出 plan mode，或自動模式的閘門檢查。

若要依每個工具呼叫接受檢查時的權限模式將其分組，請使用[工具決策事件](#tool-decision-event)上的 `permission_mode`。

**事件名稱**：`claude_code.permission_mode_changed`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"permission_mode_changed"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `from_mode`：先前的權限模式，例如 `"default"`、`"plan"`、`"acceptEdits"`、`"auto"` 或 `"bypassPermissions"`
* `to_mode`：新的權限模式
* `trigger`：造成變更的原因，例如 `"shift_tab"`、`"exit_plan_mode"` 或 `"auto_gate_denied"`。某些變更中不存在，例如 SDK 透過 [`setPermissionMode()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#query-object) 設定權限模式時

#### 身分驗證事件

在 `/login` 或 `/logout` 完成時記錄。

**事件名稱**：`claude_code.auth`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"auth"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `action`：`"login"` 或 `"logout"`
* `success`：`"true"` 或 `"false"`
* `auth_method`：身分驗證方式，例如 `"oauth"`
* `error_category`：動作失敗時的錯誤種類分類。絕不包含原始錯誤訊息
* `status_code`：動作因 HTTP 錯誤而失敗時的 HTTP 狀態碼（字串）

#### MCP 伺服器連線事件

在 MCP 伺服器連線、中斷連線或連線失敗時記錄。

**事件名稱**：`claude_code.mcp_server_connection`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"mcp_server_connection"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `status`：`"connected"`、`"failed"` 或 `"disconnected"`
* `transport_type`：伺服器傳輸方式，例如 `"stdio"`、`"sse"` 或 `"http"`
* `server_scope`：伺服器的設定範圍，例如 `"user"`、`"project"` 或 `"local"`
* `duration_ms`：連線嘗試持續時間（毫秒）
* `error_code`：連線失敗時的錯誤碼
* `is_plugin`：伺服器由外掛提供時為 `true`，否則為 `false`
* `plugin_id_hash`（當 `is_plugin` 為 `true` 時）：外掛名稱與市集的穩定雜湊值，用於依外掛將事件分組而不暴露名稱。Claude Code 依照[外掛載入事件](#plugin-loaded-event)中所述的方式計算此值
* `plugin.name`（當 `is_plugin` 為 `true` 時）：提供該伺服器之外掛的名稱。對於第三方外掛，除非設定 `OTEL_LOG_TOOL_DETAILS=1`，否則為字面字串 `"third-party"`；這可預設防止第三方外掛名稱出現在日誌中。來自 Anthropic 官方來源的外掛一律以名稱識別。`plugin_id_hash` 與 `plugin.name` 屬性會流向您自己的監控後端，不會傳送給 Anthropic
* `server_name`（當 `OTEL_LOG_TOOL_DETAILS=1` 時）：設定的伺服器名稱
* `error`（當 `OTEL_LOG_TOOL_DETAILS=1` 時）：連線失敗時的完整錯誤訊息

#### 內部錯誤事件

在 Claude Code 攔截到非預期的內部錯誤時記錄。只會記錄錯誤類別名稱與 errno 樣式的代碼。絕不包含錯誤訊息與堆疊追蹤。在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上執行時，或設定了 `DISABLE_ERROR_REPORTING` 時，不會發出此事件。

**事件名稱**：`claude_code.internal_error`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"internal_error"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `error_name`：錯誤類別名稱，例如 `"TypeError"` 或 `"SyntaxError"`
* `error_code`：錯誤上存在的 Node.js errno 代碼，例如 `"ENOENT"`

#### 外掛安裝事件

在外掛完成安裝時記錄，來源包括 `claude plugin install` CLI 命令與互動式 `/plugin` UI。

**事件名稱**：`claude_code.plugin_installed`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"plugin_installed"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `marketplace.is_official`：若市集是 Anthropic 官方市集則為 `"true"`，否則為 `"false"`
* `install.trigger`：`"cli"` 或 `"ui"`
* `plugin.name`：已安裝外掛的名稱。對於第三方市集，只有在 `OTEL_LOG_TOOL_DETAILS=1` 時才會包含
* `plugin.version`：在市集項目中宣告的外掛版本。對於第三方市集，只有在 `OTEL_LOG_TOOL_DETAILS=1` 時才會包含
* `marketplace.name`：外掛的安裝來源市集。對於第三方市集，只有在 `OTEL_LOG_TOOL_DETAILS=1` 時才會包含

#### 外掛已載入事件

在工作階段開始時，針對每個已啟用的外掛記錄一次。使用此事件盤點整個機群中有哪些外掛處於啟用狀態，作為 `plugin_installed`（記錄安裝動作本身）的補充。

**事件名稱**：`claude_code.plugin_loaded`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"plugin_loaded"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `plugin.name`：外掛名稱。對於官方市集與內建套件以外的外掛，除非設定 `OTEL_LOG_TOOL_DETAILS=1`，否則值為 `"third-party"`
* `marketplace.name`：安裝該外掛的來源市集（若已知）。在與 `plugin.name` 相同的條件下會被遮蔽為 `"third-party"`
* `plugin.version`：外掛 manifest 中的版本。僅在名稱未被遮蔽且 manifest 宣告了版本時才會包含
* `plugin.scope`：外掛的來源類別：`"official"`、`"community"`、`"org"`、`"user-local"` 或 `"default-bundle"`
* `enabled_via`：外掛被啟用的方式：`"default-enable"`、`"org-policy"`、`"admin-install"`、`"seed-mount"` 或 `"user-install"`。`"admin-install"` 值表示該外掛在[**Organization settings > Plugins & skills**](https://claude.ai/admin-settings/skills?tab=inventory) 中被設為您組織的必要安裝或自動安裝。在 v2.1.246 之前，Claude Code 會將這些外掛回報為 `"user-install"` 或 `"seed-mount"`
* `plugin_id_hash`：外掛名稱與市集的確定性雜湊值，僅傳送至您設定的匯出器。讓您可以計算整個機群中載入的不同第三方外掛數量，而無需記錄其名稱。對於[從 claude.ai 同步的外掛](https://code.claude.com/docs/zh-TW/plugins/loading.md#synced-plugins)，Claude Code 會將外掛名稱與 claude.ai 為該外掛回報的市集名稱一起雜湊，若無則使用 `synced`。在 v2.1.246 之前，Claude Code 不會在雜湊中使用 claude.ai 回報的市集名稱
* `has_hooks`：外掛是否透過 [hook 設定](https://code.claude.com/docs/zh-TW/plugins/components.md#hooks)或作為 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md#how-a-mod-works) 提供 hook
* `has_mcp`：外掛是否提供 MCP 伺服器
* `host_owned_mcp`：當 SDK 主機管理此外掛的 MCP 連線且 Claude Code 略過讀取外掛的 MCP 伺服器設定時為 `true`，否則為 `false`
* `skill_path_count`：外掛宣告的 skill 目錄數量
* `command_path_count`：外掛宣告的命令目錄數量
* `agent_path_count`：外掛宣告的 agent 目錄數量
* `safe_mode`：當工作階段以 [`--safe-mode`](https://code.claude.com/docs/zh-TW/cli-reference) 啟動時為 `"true"`，否則為 `"false"`。在安全模式下，此事件僅回報已設定的清單；外掛的命令、skill、hook 與 MCP 伺服器不會載入。需要 Claude Code v2.1.169 或更新版本

#### Skill 已啟動事件

在 skill 被叫用時記錄，無論是 Claude 透過 Skill 工具呼叫，還是您以 `/` 命令執行。

**事件名稱**：`claude_code.skill_activated`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"skill_activated"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `skill.name`：skill 的名稱。對於使用者定義及第三方外掛的 skill，除非設定 `OTEL_LOG_TOOL_DETAILS=1`，否則值為預留位置 `"custom_skill"`
* `invocation_trigger`：skill 的觸發方式（`"user-slash"`、`"claude-proactive"` 或 `"nested-skill"`）
* `skill.source`：skill 的載入來源（例如 `"bundled"`、`"userSettings"`、`"projectSettings"`、`"plugin"`）
* `skill.kind`：當 skill 為工作流程 skill 時為 `"workflow"`，否則不存在
* `plugin.name`（當設定 `OTEL_LOG_TOOL_DETAILS=1` 或外掛來自官方市集時）：當 skill 由外掛提供時，所屬外掛的名稱
* `marketplace.name`（當設定 `OTEL_LOG_TOOL_DETAILS=1` 或外掛來自官方市集時）：當 skill 由外掛提供時，安裝所屬外掛的來源市集

#### @ 提及事件

在 Claude Code 解析提示詞中的 `@` 提及時記錄。並非每個提及都會發出事件：提前結束的路徑（例如權限拒絕、檔案過大、PDF 參照附件，以及目錄列出失敗）會直接返回而不記錄。

每次 Claude Code 讀取提示詞時，`mention_type` 為 `"agent"` 的事件最多記錄 100 個，`"mcp_resource"` 的事件也最多記錄 100 個。超過任一上限的提及仍會被解析，但不會發出事件。

**事件名稱**：`claude_code.at_mention`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"at_mention"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `mention_type`：提及的類型（`"file"`、`"directory"`、`"agent"`、`"mcp_resource"`、`"peer"`）。`"peer"` 值表示您提及了[您的其他 Claude Code 工作階段之一](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)。需要 Claude Code v2.1.232 或更新版本
* `success`：提及是否成功解析（`"true"` 或 `"false"`）

#### API 重試耗盡事件

在 API 請求經過多次嘗試後仍失敗時記錄一次。與最終的 `api_error` 事件一起發出。

**事件名稱**：`claude_code.api_retries_exhausted`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"api_retries_exhausted"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `model`：使用的模型
* `error`：最終錯誤訊息
* `status_code`：HTTP 狀態碼（數字）。非 HTTP 錯誤時不存在。
* `total_attempts`：總嘗試次數
* `total_retry_duration_ms`：所有嘗試的總實際經過時間
* `speed`：`"fast"` 或 `"normal"`

#### Hook 已註冊事件

在工作階段開始時，針對每個已設定的 hook 記錄一次。使用此事件盤點整個機群中有哪些 hook 處於啟用狀態，作為每次執行的 `hook_execution_start` 與 `hook_execution_complete` 事件的補充。

**事件名稱**：`claude_code.hook_registered`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"hook_registered"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `hook_event`：hook 事件類型，例如 `"PreToolUse"` 或 `"PostToolUse"`
* `hook_type`：hook 實作類型：`"command"`、`"prompt"`、`"mcp_tool"`、`"http"` 或 `"agent"`
* `hook_source`：hook 的定義位置：`"userSettings"`、`"projectSettings"`、`"localSettings"`、`"flagSettings"`、`"policySettings"` 或 `"pluginHook"`
* `safe_mode`：當工作階段以 [`--safe-mode`](https://code.claude.com/docs/zh-TW/cli-reference) 啟動時為 `"true"`，否則為 `"false"`。需要 Claude Code v2.1.169 或更新版本
* `hook_matcher`（當設定 `OTEL_LOG_TOOL_DETAILS=1` 時）：hook 設定中的 matcher 字串（若有設定）
* `plugin.name`（當 `hook_source` 為 `"pluginHook"` 時）：提供該 hook 的外掛名稱。對於官方市集與內建套件以外的外掛，除非設定 `OTEL_LOG_TOOL_DETAILS=1`，否則值為 `"third-party"`
* `plugin_id_hash`（當 `hook_source` 為 `"pluginHook"` 時）：外掛名稱與市集的確定性雜湊值，僅傳送至您設定的匯出器。讓您可以計算提供 hook 的不同外掛數量，而無需記錄其名稱。Claude Code 的計算方式如[外掛已載入事件](#plugin-loaded-event)中所述

#### Hook 執行開始事件

在某個 hook 事件的一或多個 hook 開始執行時記錄。

**事件名稱**：`claude_code.hook_execution_start`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"hook_execution_start"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `hook_event`：hook 事件類型，例如 `"PreToolUse"` 或 `"PostToolUse"`
* `hook_name`：包含 matcher 的完整 hook 名稱，例如 `"PreToolUse:Write"`
* `num_hooks`：符合的 hook 命令數量
* `managed_only`：當僅允許受管政策 hook 時為 `"true"`
* `hook_source`：`"policySettings"` 或 `"merged"`
* `safe_mode`：當工作階段以 [`--safe-mode`](https://code.claude.com/docs/zh-TW/cli-reference) 啟動時為 `"true"`，否則為 `"false"`。需要 Claude Code v2.1.169 或更新版本
* `hook_definitions`：JSON 序列化的 hook 設定。僅在同時啟用詳細 beta 追蹤與 `OTEL_LOG_TOOL_DETAILS=1` 時才會包含

#### Hook 執行完成事件

在某個 hook 事件的所有 hook 都執行完畢時記錄。

**事件名稱**：`claude_code.hook_execution_complete`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"hook_execution_complete"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `hook_event`：hook 事件類型
* `hook_name`：包含 matcher 的完整 hook 名稱
* `num_hooks`：符合的 hook 命令數量
* `num_success`：成功完成的數量
* `num_blocking`：回傳阻擋決定的數量
* `num_non_blocking_error`：失敗但未阻擋的數量
* `num_cancelled`：在完成前被取消的數量
* `total_duration_ms`：所有符合 hook 的實際經過時間
* `stdout_chars`：成功執行的符合 hook 的 stdout 總字元數。需要 Claude Code v2.1.280 或更新版本
* `additional_context_chars`：符合 hook 所回傳的 `additionalContext` 總字元數。需要 Claude Code v2.1.280 或更新版本
* `system_message_chars`：符合 hook 所回傳的 `systemMessage` 總字元數。需要 Claude Code v2.1.280 或更新版本
* `initial_user_message_chars`：符合 hook 所回傳的 `initialUserMessage` 總字元數。需要 Claude Code v2.1.280 或更新版本
* `num_outputs_persisted`：超過 [10,000 字元上限](https://code.claude.com/docs/zh-TW/hooks.md#json-output)而被 Claude Code 儲存至檔案的 hook 輸出數量。需要 Claude Code v2.1.280 或更新版本
* `managed_only`：當僅允許受管政策 hook 時為 `"true"`
* `hook_source`：`"policySettings"` 或 `"merged"`
* `safe_mode`：當工作階段以 [`--safe-mode`](https://code.claude.com/docs/zh-TW/cli-reference) 啟動時為 `"true"`，否則為 `"false"`。需要 Claude Code v2.1.169 或更新版本
* `hook_definitions`：JSON 序列化的 hook 設定。僅在同時啟用詳細 beta 追蹤與 `OTEL_LOG_TOOL_DETAILS=1` 時才會包含

#### Hook 外掛指標事件

在官方市集外掛的 hook 發出每次叫用的指標時記錄。只有從官方 Anthropic 市集安裝的外掛才能發出這些指標。第三方市集外掛與使用者設定的 hook 不會發出此事件。使用此事件可從您自己的可觀測性堆疊監控外掛行為，例如發現率、成本與持續時間。

**事件名稱**：`claude_code.hook_plugin_metrics`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"hook_plugin_metrics"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `plugin_id`：`<name>@<marketplace>` 格式的外掛識別碼
* `hook_event`：發出指標的 hook 事件類型
* 最多 20 個由外掛發出的指標鍵。名稱須符合 `^[a-z][a-z0-9_]{0,39}$`。值為布林值或數字。

#### 壓縮事件

在對話壓縮完成時記錄。

**事件名稱**：`claude_code.compaction`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"compaction"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `trigger`：`"auto"` 或 `"manual"`
* `success`：`"true"` 或 `"false"`
* `duration_ms`：壓縮持續時間
* `pre_tokens`：壓縮前的約略 token 數
* `post_tokens`：壓縮後的約略 token 數
* `error`：壓縮失敗時的錯誤訊息
* `precompute_reuse`：僅在 `trigger` 為 `"manual"` 時設定，或在互動式終端機工作階段中針對[閒置壓縮](https://code.claude.com/docs/zh-TW/settings-reference.md#idlecompaction)而 `trigger` 為 `"auto"` 時設定。自動壓縮可在上下文視窗填滿之前於背景準備摘要，此屬性記錄壓縮是否重複使用了該預先準備的摘要。`"hit"` 表示已重複使用；`"miss_custom_instructions"`、`"miss_hook"` 與 `"miss_not_ready"` 則說明改為重新計算摘要的原因

#### Subagent 已完成事件

在 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 完成並將結果回傳給啟動它的對話時記錄。可用它依 subagent 類型彙總工具使用與執行時間；若要彙總 token 或成本，請使用篩選 `query_source` 為 `"subagent"` 的 [token 計數器](#token-counter)與[成本計數器](#cost-counter)，因為此事件的 `total_tokens` 僅涵蓋最後一次請求。`"subagent"` 類別也會計入來自以 agent 為基礎的 hook 的請求，而這些 hook 不會發出 subagent 事件。

**事件名稱**：`claude_code.subagent_completed`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"subagent_completed"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `agent_type`：subagent 類型。內建 agent 名稱及來自官方市集外掛的 agent 會原樣顯示；除非設定 `OTEL_LOG_TOOL_DETAILS=1`，否則其他 agent 名稱會被替換為 `"custom"`
* `agent.source`：agent 定義的來源：`built-in`、`plugin`，或定義自訂 agent 的設定來源，例如 `userSettings` 或 `projectSettings`
* `is_built_in`：subagent 是否為內建 agent 類型
* `is_async`：subagent 是否在[背景](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)執行
* `total_tokens`：subagent 最後一次 API 請求的 token 用量：該次請求的輸入、快取建立、快取讀取與輸出 token，大致相當於 subagent 完成時的上下文大小。並非整個執行過程的總和
* `total_tool_uses`：subagent 在整個執行過程中進行的工具呼叫次數
* `duration_ms`：執行時間（毫秒）
* `model`：subagent 被解析要執行的模型
* `final_model`：產生 subagent 最終回應的模型，在執行途中切換（例如改用備援模型）後會與 `model` 不同
* `model_swapped`：是否有多個模型處理了 subagent 的請求
* `plugin_id_hash`、`plugin.name`：外掛提供的 agent 才會存在。官方市集外掛名稱會原樣顯示；除非設定 `OTEL_LOG_TOOL_DETAILS=1`，否則其他外掛名稱會被替換為 `"third-party"`

#### 意見回饋調查事件

在顯示或回答工作階段品質調查時記錄。關於調查收集的內容及控制方式，請參閱[工作階段品質調查](https://code.claude.com/docs/zh-TW/data-usage.md#session-quality-surveys)。

**事件名稱**：`claude_code.feedback_survey`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"feedback_survey"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `event_type`：調查生命週期事件，例如 `"appeared"`、`"responded"` 或 `"transcript_prompt_appeared"`
* `appearance_id`：連結同一調查實例所發出事件的唯一 ID
* `survey_type`：產生事件的調查。`"session"` 為「How is Claude doing?」評分提示
* `response`：`responded` 事件中使用者的選擇
* `enabled_via_override`：當設定 [`CLAUDE_CODE_ENABLE_FEEDBACK_SURVEY_FOR_OTEL`](https://code.claude.com/docs/zh-TW/env-vars) 時為 `true`。以布林值而非字串發出。存在於 `session` 調查事件中。可篩選此屬性以確認覆寫已套用至整個機群

#### 保留清理事件

在每次執行保留清理時記錄一次，該清理會刪除早於 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) 設定的[工作階段逐字稿及其他應用程式資料](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)。Claude Code 每個工作階段最多在背景執行一次清理，即使沒有刪除任何項目也仍會發出事件。若 Claude Code 在過去 24 小時內已在同一台機器上的任何工作階段中執行過清理，則會將此工作階段的清理延遲至少 10 分鐘，因此較早結束的工作階段不會發出任何事件。當您以 `--bare` 執行 `claude -p` 時，Claude Code 不會執行清理，也不會發出任何事件。

如同本頁上的所有 OTel 事件，此事件僅傳送至您設定的遙測後端。需要 Claude Code v2.1.227 或更新版本。

當 Claude Code 無法安全地判斷保留期間時，會暫停清理並發出 `result` 設為 `"skipped"` 且附有 `skip_reason` 的事件。當[受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)設定了 `cleanupPeriodDays` 時，受管值會固定保留期間，即使較低優先順序範圍中的設定檔損壞或無效，清理仍會執行。當 `managed-settings.json` 本身無法讀取時，除非[受管層級](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)從其他地方（例如伺服器受管設定或損壞檔案旁的 `managed-settings.d/` drop-in）提供 `cleanupPeriodDays`，否則 Claude Code 仍會暫停清理。刪除計數器屬性僅在 `result` 為 `"complete"` 時存在。

**事件名稱**：`claude_code.retention_sweep`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"retention_sweep"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `result`：清理已執行時為 `"complete"`，Claude Code 暫停清理時為 `"skipped"`
* `period_days`：合併後設定中的 `cleanupPeriodDays` 值（以天為單位），若無任何來源設定則為 `30`。在 skipped 事件中，為清理原本會使用的值，依 Claude Code 可讀取的設定來源計算
* `used_default`：當沒有任何可讀取的設定來源設定 `cleanupPeriodDays` 時為 `"true"`，否則為 `"false"`。在 complete 事件中，`"true"` 表示套用了 30 天的預設值
* `skip_reason`：Claude Code 暫停清理的原因。僅在 `result` 為 `"skipped"` 時存在：
  * `"user_source_disabled"`：使用者設定被排除，例如透過 [`--setting-sources`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 旗標或 SDK 的 [`settingSources`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 選項，且沒有已啟用的來源提供 `cleanupPeriodDays`
  * `"settings_unknowable"`：某個設定檔無法讀取或剖析，因此 `cleanupPeriodDays` 或 `desktopSessionCleanupPeriodDays` 可能被設定為 Claude Code 看不到的值
  * `"settings_invalid_key_set"`：設定有驗證錯誤，且明確設定了 `cleanupPeriodDays` 或 `desktopSessionCleanupPeriodDays`，因此改用預設值可能會違背該設定而刪除或保留檔案
  * `"remote_settings_unknowable"`：第三方部署上 Claude Desktop 的 Code 分頁中的工作階段請求了[伺服器受管設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)。它未收到可用的回應，因此 `cleanupPeriodDays` 可能被設定為 Claude Code 看不到的值
* `transcripts_deleted`：清理所刪除的工作階段逐字稿（即最上層的 `~/.claude/projects/*/*.jsonl` 檔案）數量
* `transcripts_exempted_desktop`：超過保留期間但依 [Claude Desktop 與 Cowork 規則](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)被清理保留的逐字稿數量。這些不會計入 `files_past_cutoff`。需要 Claude Code v2.1.248 或更新版本
* `session_files_deleted`：工作階段檔案清理所刪除的項目數量：逐字稿加上每個工作階段的附屬檔案，例如 sidecar、錄製內容與工具結果
* `artifacts_deleted`：清理在其涵蓋的資料目錄中刪除的項目總數，包括工作階段檔案。某些清理會將整個被移除的目錄樹計為一個項目，且少數清理流程不會計入此計數器，因此請將此值視為下限，而非精確的檔案數量
* `files_retained_fresh`：已檢查但因仍在保留期間內而保留的檔案。僅逐檔清理會計入這些檔案，因此此值為下限；非零值為正常的穩定狀態
* `files_past_cutoff`：早於保留期間但清理未能刪除的檔案，例如因為權限錯誤或檔案仍被開啟。此計數也包括清理在 `skills/synced/` 或 `plugins/synced/` 下找到的每個過期資料夾，無論是否已將該資料夾移至垃圾桶。除了這些資料夾之外，大於零的值表示有檔案超過了設定的保留期間仍存在；零並不代表沒有這種情況，因為整個目錄移除失敗會改為計入 `error_count`
* `error_count`：清理在列出或刪除檔案時遇到的錯誤數量

#### 受管設定已解析事件

記錄工作階段所解析的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)：在工作階段開始時記錄一次，在工作階段期間受管設定或[政策輔助程式](https://code.claude.com/docs/zh-TW/managed-settings.md#compute-the-policy-with-a-helper-program)的狀態變更時再次記錄，以及在 Claude Code 因 `error.type` 屬性所列的原因之一而拒絕啟動或結束工作階段時記錄。
使用此事件可找出在非預期受管來源上執行的機器、政策輔助程式失敗的機器，以及機器拒絕啟動的原因。
需要 Claude Code v2.1.274 或更新版本。

預設情況下，此事件會攜帶受管來源與政策輔助程式的狀態，但不包含設定本身。若要加入經遮蔽的 `managed_settings.settings` 屬性及 `managed_settings.resolved_sha256` 摘要，請設定 `OTEL_LOG_MANAGED_SETTINGS=1`：

* 在受管設定、使用者設定或 `--settings` 的 `env` 區塊中設定，或在您啟動 Claude Code 的環境中設定。專案或本機設定中的值不會啟用它，因為複製的儲存庫可以寫入這些設定。
* 伺服器受管設定可以設定它而不會顯示[安全核准對話框](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)，因為此變數只會將您組織自己經遮蔽的政策加入您組織已經收到的事件中。

在您尚未[信任](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)的資料夾中的互動式工作階段裡，Claude Code 不會匯出拒絕事件。

**事件名稱**：`claude_code.managed_settings_resolved`

**屬性**：

* 所有[標準屬性](#standard-attributes)
* `event.name`：`"managed_settings_resolved"`
* `event.timestamp`：ISO 8601 時間戳記
* `event.sequence`：用於排序事件的每個程序計數器，說明請見[事件關聯屬性](#event-correlation-attributes)
* `managed_settings.trigger`：工作階段開始事件為 `"startup"`，在工作階段稍後受管設定或政策輔助程式狀態變更時為 `"change"`，受管設定政策停止工作階段時為 `"refused"`。Claude Code 僅在某個屬性與上次傳送的事件不同時才傳送 `change` 事件，且即使 `OTEL_LOG_MANAGED_SETTINGS` 關閉，設定值的變更仍會計入
* `error.type`：Claude Code 停止工作階段的原因。僅存在於 `refused` 事件中：
  * `"helper_failed"`：[政策輔助程式執行失敗](https://code.claude.com/docs/zh-TW/settings-reference.md#helper-failures)
  * `"policy_invalid"`：受管設定包含使 Claude Code 無法啟動的錯誤，或某個管理來源因讀取被拒以外的原因載入失敗，導致 Claude Code 無法檢查組織登入或提供者強制執行
  * `"provider_not_allowed"`：工作階段將使用受管 [`allowedProviders`](https://code.claude.com/docs/zh-TW/settings-reference#allowedproviders) 清單不允許的 API 提供者，或將提供者的流量傳送至不允許的主機。需要 Claude Code v2.1.285 或更新版本
  * `"consent_rejected"`：使用者拒絕了伺服器受管設定的[安全核准對話框](https://code.claude.com/docs/zh-TW/server-managed-settings.md#security-approval-dialogs)
  * `"force_refresh_failed"`：[`forceRemoteSettingsRefresh`](https://code.claude.com/docs/zh-TW/settings-reference#forceremotesettingsrefresh) 所要求的設定擷取失敗
  * `"gateway_rejected"`：[Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)以 HTTP 403 回應受管設定載入
  * `"version_below_minimum"`：此版本的 Claude Code 低於 [`requiredMinimumVersion`](https://code.claude.com/docs/zh-TW/settings-reference#requiredminimumversion) 或高於 [`requiredMaximumVersion`](https://code.claude.com/docs/zh-TW/settings-reference#requiredmaximumversion)
  * `"_OTHER"`：Claude apps 閘道受管設定因其他原因載入失敗
* `managed_settings.sources`：每個提供至少一個[政策鍵](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)的受管來源，依優先順序由高至低排列，包括其鍵在 `first-wins` 下未生效的來源。值為 `"remote"`；MDM 或作業系統層級政策為 `"plist"` 或 `"hklm"`；受管設定檔與 drop-in 為 `"file"`；[嵌入主機](https://code.claude.com/docs/zh-TW/managed-settings.md#let-an-embedding-host-add-policy)提供設定時為 `"parent"`；當 Claude Code [讀取](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources) [Windows HKCU 登錄值](https://code.claude.com/docs/zh-TW/managed-settings.md#where-each-mechanism-stores-the-policy)時為 `"hkcu"`。僅攜帶控制鍵或 Claude Code 無法讀取的來源不會列出。以字串陣列發出，若沒有任何受管來源提供政策鍵則為空陣列
* `managed_settings.source_behavior`：Claude Code 讀取到的 [`managedSourcesBehavior`](https://code.claude.com/docs/zh-TW/settings-reference#managedsourcesbehavior) 值，`"first-wins"` 或 `"merge"`。若無任何來源設定此鍵則為 `"first-wins"`
* `managed_settings.helper.state`：所選 MDM 或檔案來源所設定的政策輔助程式狀態：
  * `"ok"`：輔助程式的輸出作為受管設定
  * `"bad_path"`、`"not_a_file"`、`"exit_nonzero"`、`"timed_out"`、`"oversize"`、`"parse_failed"`、`"envelope_invalid"` 或 `"schema_rejected"`：輔助程式的上次執行失敗。[輔助程式失敗](https://code.claude.com/docs/zh-TW/settings-reference.md#helper-failures)說明了各種情況
  * `"none"`：未設定輔助程式，或設定它的來源不是 MDM 政策或受管設定檔
* `managed_settings.helper.applied`：當輔助程式本身的輸出作為受管設定時為 `"output"`，否則為 `"none"`
* `managed_settings.helper.entry`：當 Claude Code 選擇了 [`policyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper) 時為 `"policyHelper"`。未選擇輔助程式時不存在
* `managed_settings.helper.path`：輔助程式所設定的 [`path`](https://code.claude.com/docs/zh-TW/settings-reference#policyhelper-path)。只要 Claude Code 選擇了輔助程式就會存在，無論是否設定 `OTEL_LOG_MANAGED_SETTINGS`
* `managed_settings.resolved_sha256`（當設定 `OTEL_LOG_MANAGED_SETTINGS=1` 時）：遮蔽前已解析受管設定的 SHA-256，以 JSON 序列化，鍵遞迴排序且不含空白。摘要相同的機器執行相同的政策。Claude Code 僅在選擇加入時才傳送摘要，因為簡短的政策可透過雜湊猜測值而被還原。若沒有解析任何受管設定，以及在 `refused` 事件中，則不存在
* `managed_settings.settings`（當設定 `OTEL_LOG_MANAGED_SETTINGS=1` 時）：已解析受管設定的名稱與結構，以 JSON 字串表示，值已遮蔽。在 `refused` 事件中不存在。Claude Code 依據其設定 schema 建立此值：

  * schema 宣告的設定名稱會被匯出，未宣告的鍵則會被省略
  * 布林值、數字，以及 schema 限制為固定選項集合的字串值（例如 `permissions.defaultMode`）會原樣匯出。`sandbox.network.httpProxyPort` 與 `sandbox.network.socksProxyPort` 會匯出為 `"[REDACTED]"`
  * 其他所有字串，例如 `model`、`apiKeyHelper`、每個 `env` 值、每個 URL 及每個命令，都會匯出為 `"[REDACTED]"`
  * 對應表的項目名稱，例如 `env` 變數名稱與外掛 ID，會原樣匯出。schema 未定義項目型別的設定（例如 `vimInsertModeRemaps`）會匯出為單一的 `"[REDACTED]"`，而 `sandbox.ignoreViolations` 會匯出為其路徑清單的清單，不含命令模式
  * 清單會保留其長度，每個項目依相同規則遮蔽
  * 當工具內建於此版本的 Claude Code，或為 `mcp__` 參照（例如 `mcp__jira__create_issue`）時，`permissions.allow`、`permissions.deny` 或 `permissions.ask` 規則會匯出為其工具名稱並遮蔽內容，例如 `Read([REDACTED])`。其他任何規則則匯出為 `"[REDACTED]"`
  * Hook 遵循相同規則，因此固定選項與數值欄位（例如 `type` 與 `timeout`）會顯示，而每個命令、URL、`matcher` 及 `if` 條件都會匯出為 `"[REDACTED]"`

  例如，含有 `apiKeyHelper`、兩個 `env` 變數及一條拒絕規則的受管設定會匯出為 `{"apiKeyHelper":"[REDACTED]","env":{"HTTPS_PROXY":"[REDACTED]","CLAUDE_CODE_ENABLE_TELEMETRY":"[REDACTED]"},"permissions":{"deny":["Read([REDACTED])"]}}`。

  Claude Code 會在 UTF-8 的 8 KB 處截斷此值，截斷後的值不是有效的 JSON
* `managed_settings.settings_truncated`（當 `managed_settings.settings` 存在時）：當 Claude Code 在 8 KB 處截斷 `managed_settings.settings` 時為 `true`，否則為 `false`。以布林值而非字串發出

## 解釋指標和事件資料

匯出的指標和事件支援一系列分析：

### 使用情況監控

| 指標 | 分析機會 |
| - | - |
| `claude_code.token.usage` | 按 token [`type`](#token-counter)、使用者、團隊、模型、`skill.name`、`plugin.name` 或 `agent.name` 進行細分 |
| `claude_code.session.count` | 追蹤一段時間內的採用和參與度 |
| `claude_code.lines_of_code.count` | 透過追蹤程式碼新增和移除來衡量生產力，按模型進行細分 |
| `claude_code.commit.count` & `claude_code.pull_request.count` | 了解對開發工作流程的影響 |

### 成本監控

`claude_code.cost.usage` 指標有助於：

* 追蹤跨團隊或個人的使用趨勢
* 識別高使用量工作階段以進行最佳化
* 透過 `skill.name`、`plugin.name` 和 `agent.name` 屬性將支出歸因於特定技能、外掛程式或子代理類型

> [!NOTE]
>
> 成本指標是近似值。如需官方計費資料，請參閱[管理組織的成本](https://code.claude.com/docs/zh-TW/costs.md#manage-costs-for-your-organization)。

Claude Code 將每個串流回應計入成本和 token 指標中恰好一次，包括當 `ANTHROPIC_BASE_URL` 後方的閘道或代理伺服器跨多個框架逐步串流使用情況時。

### 警報和分段

要考慮的常見警報：

* 成本尖峰
* 異常的權杖消耗
* 來自特定使用者的高工作階段量

所有指標都可以按[標準屬性](#standard-attributes)進行分段。`model` 屬性可在 `claude_code.token.usage`、`claude_code.cost.usage` 和 `claude_code.lines_of_code.count` 上使用。

提交的按模型細分只能透過在 `session.id` 上與權杖或成本指標進行聯接來近似，因為一個工作階段可以跨越多個模型。篩選權杖或成本端的列，使 `query_source` 為 `"main"`，以便輔助和子代理請求不會將工作階段的提交歸因於未進行提交的模型。

### 偵測重試耗盡

Claude Code 在內部重試失敗的 API 請求，並僅在放棄後才發出單個 `claude_code.api_error` 事件，因此事件本身是該請求的終端訊號。中間重試嘗試不會作為單獨的事件記錄。

事件上的 `attempt` 屬性記錄嘗試次數。`CLAUDE_CODE_MAX_RETRIES` 預設為 10，上限為 15；若設定了 [`CLAUDE_CODE_RETRY_WATCHDOG`](https://code.claude.com/docs/zh-TW/env-vars)，預設值會更高且沒有上限。

當請求在暫時性錯誤上耗盡所有重試時，`attempt` 最多為該有效限制加一：預設為 11。

較低的值仍可能表示重試已用盡：每次 Claude Code 在串流失敗後重新發出請求時，`attempt` 都會從 `1` 重新開始計算。

若要區分從一個恢復的工作階段與停滯的工作階段，請按 `session.id` 分組事件，並檢查錯誤後是否存在更晚的 `api_request` 事件。

### 事件分析

事件資料提供了對 Claude Code 互動的詳細見解：

**工具使用模式**：分析工具結果事件以識別：

* 最常使用的工具
* 工具成功率
* 平均工具執行時間
* 按工具類型的錯誤模式

**效能監控**：追蹤 API 請求持續時間和工具執行時間以識別效能瓶頸。

### 將輸入 token 對應至 OpenTelemetry GenAI 語意慣例

Claude Code 依照 API 回應的 usage 區塊中所呈現的方式匯出輸入 token 計數，因此這些值不包含從[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)讀取或寫入的 token：

* [`claude_code.llm_request`](#span-attributes) span 和 [`api_request`](#api-request-event) 事件上的 `input_tokens`
* [`claude_code.token.usage`](#token-counter) 指標的 `"input"` 類型

Claude Code 不會設定 `gen_ai.usage.*` 屬性。[OpenTelemetry GenAI 語意慣例](https://github.com/open-telemetry/semantic-conventions-genai)規定 `gen_ai.usage.input_tokens` 應包含從快取讀取和寫入快取的 token。若要計算該總數：

* 從 span 或事件：將 `input_tokens`、`cache_read_tokens` 和 `cache_creation_tokens` 相加
* 從 `claude_code.token.usage` 指標：將其 `"input"`、`"cacheRead"` 和 `"cacheCreation"` 類型相加

這些慣例也為快取讀取和快取寫入定義了個別的屬性：

* `cache_read_tokens` 對應至 `gen_ai.usage.cache_read.input_tokens`
* `cache_creation_tokens` 對應至 `gen_ai.usage.cache_write.input_tokens`。較舊版本的慣例將快取寫入屬性命名為 `gen_ai.usage.cache_creation.input_tokens`，因此請使用您的後端所預期的名稱。

## 稽核安全事件

OpenTelemetry 事件是 Claude Code 活動的稽核資料來源。每個事件都帶有身份屬性，將工具呼叫、MCP 活動和權限決定與觸發它們的使用者相關聯。OTLP 日誌匯出器可以將這些事件傳遞到任何具有 OTLP 接收器的安全資訊和事件管理 (SIEM) 平台，或轉發到您的 SIEM 的 OpenTelemetry Collector。

### 將屬性操作歸因於使用者

每個事件上的[標準屬性](#standard-attributes)包括已驗證使用者的身份：使用 Claude 帳戶登入時的 `user.email`、`user.account_uuid`、`user.account_id` 和 `organization.id`，或在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，當工作階段自身的認證攜帶它們時，加上 `user.id` 和每個工作階段的 `session.id`。`user.id` 是安裝範圍的識別碼，除了在 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段上透過 `/login` 登入時，其中它是來自閘道簽發令牌的 IdP 主體。

在一個開發人員啟動的工作階段中，MCP 工具呼叫、Bash 命令和檔案編輯因此歸因於該開發人員。Claude Code 不在單獨的服務帳戶下運作；每個事件上記錄的身份是開發人員自己的 Claude 帳戶，或開發人員在 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段上的 IdP 身份。在 Claude Tag 頻道工作階段中，Claude 改為以您組織的[共用身份](https://code.claude.com/docs/zh-TW/cloud-environments.md#set-the-environment-a-claude-tag-channel-uses)運作。

當 Claude Code 使用直接 API 金鑰進行身份驗證，或針對 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 進行身份驗證時，工作階段中沒有 Claude 帳戶，僅填充 `user.id` 和 `session.id`。在這些部署中，使用 `OTEL_RESOURCE_ATTRIBUTES` 自行附加使用者身份，透過[受管設定](#administrator-configuration)檔案或啟動包裝器按使用者設定。Claude apps gateway 工作階段不需要任何這些：請參閱[標準屬性](#standard-attributes)以了解其匯出所攜帶的身份。

```bash theme={null}
export OTEL_RESOURCE_ATTRIBUTES="enduser.id=jdoe@example.com,enduser.directory_id=S-1-5-21-..."
```

### 稽核 MCP 活動

若要使用完整呼叫詳情捕捉 MCP 伺服器活動，請啟用日誌匯出器並設定 `OTEL_LOG_TOOL_DETAILS=1`。每個 MCP 操作然後產生結構化事件，其中包含伺服器名稱、工具名稱和呼叫引數以及標準身份屬性：

| 事件 | 它為 MCP 記錄的內容 |
| - | - |
| `mcp_server_connection` | 伺服器連線、斷開連線和連線失敗，包含 `server_name`、`transport_type`、`server_scope` 和錯誤詳情 |
| `tool_result` | 每個 MCP 工具呼叫，包含 `tool_name` 和 `mcp_server_scope`、包含 `mcp_server_name` 和 `mcp_tool_name` 的 `tool_parameters` 承載，以及包含呼叫引數的 `tool_input` 承載 |
| `tool_decision` | 呼叫是否被允許或拒絕，以及決定是來自配置、hook 還是使用者，以及包含 `mcp_server_name` 和 `mcp_tool_name` 的 `tool_parameters` 承載 |

沒有 `OTEL_LOG_TOOL_DETAILS`，這些事件會捨棄識別詳情：

* `tool_result`：保留 `mcp_server_scope` 和 `tool_name` 對使用者設定的伺服器編輯為字面上的 `"mcp_tool"`，省略引數內容。對於 Claude Desktop 的內建伺服器，在 Claude Desktop 擁有的工作階段中，它也保留 `tool_parameters` 內的 `mcp_server_name`/`mcp_tool_name` 配對，與 `tool_decision` 相同的主機編寫例外
* `tool_decision`：保留 `tool_source` 和 `tool_name` 對使用者設定的伺服器編輯為字面上的 `"mcp_tool"`，省略引數內容。對於 Claude Desktop 的內建伺服器，在 Claude Desktop 擁有的工作階段中，它也保留 `tool_parameters` 內的 `mcp_server_name`/`mcp_tool_name` 配對
* `mcp_server_connection`：省略 `server_name` 和錯誤訊息，但保留 `is_plugin`、`plugin_id_hash` 和 `plugin.name`，非 Anthropic plugin 名稱被編輯為字面上的 `"third-party"`，因此 plugin 提供的伺服器在沒有詳細日誌的情況下仍然可以區分

### 將安全問題對應到事件

建立偵測規則時，查詢您想要監控的訊號並查詢您的後端以取得相應的事件和屬性：

| 訊號 | 事件 | 關鍵屬性 |
| - | - | - |
| 工具呼叫被允許或拒絕，以及決定的來源，例如設定、hook 或使用者 | [`tool_decision`](#tool-decision-event) | `decision`、`source`、`classifier_verdict`、`permission_mode`、`tool_name`；設定 `OTEL_LOG_TOOL_DETAILS=1` 時另有 `tool_parameters` |
| 哪項檢查拒絕了工具呼叫，或要求為其顯示權限提示 | [`safety_event`](#safety-event)，其中 `category` 指出該檢查，例如 `"managed_policy"`、`"permission_rule"`、`"hook"` 或 `"auto_mode_block"`。對於未執行的呼叫，`decision` 為 `"reject"`。部分呼叫[沒有 safety event](#calls-without-a-safety-event) | `category`、`decision`、`reason_code`、`rule_source`、`tool_name`、`tool_use_id` |
| 自動模式分類器允許或封鎖了工具呼叫，或 Claude Code 在沒有分類器判定的情況下拒絕了呼叫 | 含有 `classifier_verdict` 的 [`tool_decision`](#tool-decision-event)。對於沒有判定的拒絕，`classifier_verdict` 為 `"no_verdict"` 或 `"unavailable"` | `classifier_verdict`、`permission_mode`、`tool_name`；設定 `OTEL_LOG_TOOL_DETAILS=1` 時另有 `classifier_category` |
| 權限模式升級 | `permission_mode_changed` | `from_mode`、`to_mode`、`trigger` |
| 每個工具呼叫是在哪個權限模式下檢查的，包括 subagent 發出的呼叫 | [`tool_decision`](#tool-decision-event) | `permission_mode`、`session.id` |
| 原則 hook 阻止了操作 | `hook_execution_complete` | `hook_event`、`num_blocking` |
| hook 拒絕了哪個工具呼叫，以及 hook 封鎖了哪個結果或回合結束 | [`safety_event`](#safety-event)，其中對於被拒絕的呼叫，`category` 為 `"hook"` 且 `decision` 為 `"reject"`；對於被封鎖的結果或回合結束，`category` 為 `"hook_review"` | `category`、`decision`、`hook_event`；工具呼叫另有 `tool_use_id` |
| 沙箱的網路代理伺服器拒絕了來自 Bash 或 PowerShell 命令的連線或請求 | [`safety_event`](#safety-event)，其中 `sandbox_violation_count` 存在且不為 `"0"` | `sandbox_violation_count`、`category`、`sandbox_enabled`、`tool_use_id` |
| 登入、登出和身份驗證失敗 | `auth` | `action`、`success`、`error_category` |
| MCP 伺服器連線或失敗 | `mcp_server_connection` | `status`、`server_name`、`is_plugin`、`error_code` |
| Plugin 已安裝及其來源 | `plugin_installed` | `plugin.name`、`marketplace.name`、`marketplace.is_official` |
| 執行的命令和觸及的檔案 | `tool_result`（已執行）或 `tool_decision`（已拒絕）搭配 `OTEL_LOG_TOOL_DETAILS=1` | `tool_parameters`；`tool_input`（僅限 `tool_result`） |
| 受管設定來源機器執行的內容、其原則協助程式是否健康，以及機器拒絕啟動的原因 | `managed_settings_resolved` | `managed_settings.trigger`、`managed_settings.sources`、`managed_settings.source_behavior`、`managed_settings.helper.state`、`error.type`；`managed_settings.settings` 和 `managed_settings.resolved_sha256` 搭配 `OTEL_LOG_MANAGED_SETTINGS=1` |

Claude Code 僅發出原始事件流。異常偵測、基線設定、跨工作階段關聯和警報是您的 SIEM 或可觀測性後端的責任。

### 將外送路徑對應到受管控制項和事件

下表將可能把工作階段內容帶離機器的路徑（以及本機保留）與限制它們的[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)鍵和記錄它們的事件配對。關於 Claude Code 本身傳送給 Anthropic 的內容（例如 `/feedback` 報告），請參閱[資料使用](https://code.claude.com/docs/zh-TW/data-usage.md)。各名稱連結至其參考項目，其中提供值和預設值。

| 路徑 | 受管控制項 | 事件 |
| - | - | - |
| Bash 和 PowerShell 命令 | [`sandbox.enabled`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-enabled)、[`sandbox.failIfUnavailable`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-failifunavailable)、[`sandbox.allowUnsandboxedCommands`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-allowunsandboxedcommands)、[`sandbox.network.allowManagedDomainsOnly`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-allowmanageddomainsonly)、[`sandbox.network.allowedDomains`](https://code.claude.com/docs/zh-TW/settings-reference#sandbox-network-alloweddomains) | [`tool_decision`](#tool-decision-event)、[`tool_result`](#tool-result-event) |
| MCP 伺服器 | [`allowedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#allowedmcpservers)、[`allowManagedMcpServersOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedmcpserversonly)、[`deniedMcpServers`](https://code.claude.com/docs/zh-TW/settings-reference#deniedmcpservers)、[`managed-mcp.json`](https://code.claude.com/docs/zh-TW/managed-mcp) | [`mcp_server_connection`](#mcp-server-connection-event)、`tool_decision`、`tool_result` |
| Hook | [`allowManagedHooksOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedhooksonly)、[`allowedHttpHookUrls`](https://code.claude.com/docs/zh-TW/settings-reference#allowedhttphookurls) | [`hook_registered`](#hook-registered-event)、[`hook_execution_start`](#hook-execution-start-event)、[`hook_execution_complete`](#hook-execution-complete-event) |
| 外掛 | [`strictKnownMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#strictknownmarketplaces)、[`disableSideloadFlags`](https://code.claude.com/docs/zh-TW/settings-reference#disablesideloadflags)、[`syncClaudeAiPlugins`](https://code.claude.com/docs/zh-TW/settings-reference#syncclaudeaiplugins)、[`syncClaudeAiSkills`](https://code.claude.com/docs/zh-TW/settings-reference#syncclaudeaiskills) | [`plugin_installed`](#plugin-installed-event)、[`plugin_loaded`](#plugin-loaded-event) |
| [WebFetch](https://code.claude.com/docs/zh-TW/permissions.md#webfetch) | [`permissions.deny`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-deny)、[`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly) | `tool_decision`、`tool_result` |
| 上傳至 claude.ai 的工具，例如 Artifact | `permissions.deny`、[`enableArtifact`](https://code.claude.com/docs/zh-TW/settings-reference#enableartifact) | `tool_decision`、`tool_result` |
| Remote Control | [`disableRemoteControl`](https://code.claude.com/docs/zh-TW/settings-reference#disableremotecontrol) | 無專用事件 |
| 本機逐字稿保留 | [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays) | [`retention_sweep`](#retention-sweep-event) |

`allowedHttpHookUrls`、`managed-mcp.json` 和 hook 事件項目需要表格所示以外的說明：

* **`allowedHttpHookUrls`**：項目會跨設定檔合併，因此開發人員可以在空白的受管清單中新增項目。`allowManagedHooksOnly` 決定哪些 hook 會執行
* **`managed-mcp.json`**：若要關閉 MCP，請參閱[完全停用 MCP](https://code.claude.com/docs/zh-TW/managed-mcp.md#disable-mcp-entirely)。若要確認 Claude Code 會讀取該檔案，請參閱[驗證設定](https://code.claude.com/docs/zh-TW/managed-mcp.md#validate-the-configuration)
* **Hook 事件**：Claude Code 會針對每個 hook 事件記錄一次 `hook_execution_start` 和 `hook_execution_complete`，涵蓋所有相符的 hook。單獨使用 `OTEL_LOG_TOOL_DETAILS=1` 不會記錄 HTTP hook 的 URL。hook 設定僅出現在 `hook_definitions` 中，這還需要詳細的 beta 追蹤

`OTEL_LOG_TOOL_DETAILS=1` 會將命令字串、伺服器和工具名稱以及工具輸入加入這些事件中。這些詳情可能包含與工作階段本身相同的敏感內容，因此請僅在您的收集器獲准保存該內容時才啟用它。

### 檢查保留清理

若要讓每台機器使用相同的保留期間，請在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定 [`cleanupPeriodDays`](https://code.claude.com/docs/zh-TW/settings-reference#cleanupperioddays)。若要檢查機器是否以該值執行清理，請收集 [`retention_sweep`](#retention-sweep-event) 事件。`period_days` 和各計數器是字串，因此請在比較之前將它們轉換為數字。

| 機器回報的內容 | 其意義 |
| - | - |
| `result` 為 `"skipped"` | Claude Code 暫停了清理。`skip_reason` 提供原因 |
| `used_default` 為 `"true"`，或 `period_days` 與您的受管值不同 | 該機器未套用您受管的 `cleanupPeriodDays` |
| `error_count` 大於零 | 清理在列出或刪除檔案時發生錯誤，因此超過保留期間的資料可能仍然存在 |
| `files_past_cutoff` 大於零 | 清理未能刪除超過保留期間的檔案，或發現了過時的已同步 skills 和 plugins 資料夾。請搭配 `error_count` 一起判讀 |
| 沒有事件 | 本身不代表失敗 |

正常運作的機器可能因以下原因而沒有事件：

* **沒有人啟動 Claude Code**：不會執行清理，機器會保留其資料直到下次啟動
* **工作階段持續開啟**：Claude Code 每個工作階段最多執行一次清理
* **工作階段提早結束**：工作階段結束時尚未完成的清理不會發出任何內容，因意外錯誤而停止的清理也不會

清理並未涵蓋所有路徑。[保留直到您刪除](https://code.claude.com/docs/zh-TW/claude-directory.md#kept-until-you-delete-them)列出了會保留的內容，[清除本機資料](https://code.claude.com/docs/zh-TW/claude-directory.md#clear-local-data)則說明如何移除它們。

### 將事件傳送到 SIEM

將 `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` 指向您的 SIEM 的 OTLP 接收器，或指向轉發到您的 SIEM 的原生擷取 API 的 OpenTelemetry Collector。以下受管設定範例僅匯出事件，並啟用完整工具詳情以進行 MCP 和 Bash 稽核：

```json theme={null}
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_LOG_TOOL_DETAILS": "1",
    "OTEL_EXPORTER_OTLP_LOGS_PROTOCOL": "http/protobuf",
    "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT": "https://siem.example.com:4318/v1/logs",
    "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer your-siem-token"
  }
}
```

若要確認事件已到達，請在執行此設定的工作階段中提交提示，並檢查您的 SIEM 是否有 `claude_code.user_prompt` 事件。如果沒有任何內容到達，請執行 `claude --debug-file <path>` 並檢查該日誌中的 `[3P telemetry]` 匯出錯誤。

## 後端考量

您選擇的指標、日誌和追蹤後端決定了您可以執行的分析類型：

### 指標後端

* **時間序列資料庫**：速率計算、聚合指標
* **欄式存儲**：複雜查詢、唯一使用者分析
* **功能完整的可觀測性平台**：進階查詢、視覺化、警報

### 事件和日誌後端

* **日誌聚合系統**：全文搜尋、日誌分析
* **欄式存儲**：結構化事件分析
* **功能完整的可觀測性平台**：指標和事件之間的關聯

### 追蹤後端

選擇支援分散式追蹤儲存和跨度關聯的後端：

* **分散式追蹤系統**：跨度視覺化、請求瀑布圖、延遲分析
* **功能完整的可觀測性平台**：追蹤搜尋和與指標和日誌的關聯

對於需要日活躍使用者/週活躍使用者/月活躍使用者 (DAU/WAU/MAU) 指標的組織，請考慮支援高效唯一值查詢的後端。

## 服務資訊

所有指標和事件都使用以下資源屬性匯出：

* `service.name`：終端機工作階段為 `claude-code`，從 [Claude Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md)中的 Code 標籤啟動的本機工作階段為 `claude-code-desktop`
* `service.version`：目前的 Claude Code 版本，或本機 Code 標籤工作階段的 Desktop 應用程式版本
* `os.type`：作業系統類型（例如，`linux`、`darwin`、`windows`）
* `os.version`：作業系統版本字串
* `host.arch`：主機架構（例如，`amd64`、`arm64`）
* `wsl.version`：WSL 版本號（僅在 Windows Subsystem for Linux 上執行時出現）
* 計量器名稱：`com.anthropic.claude_code`

如果您的收集器管道或儀表板在 `service.name = claude-code` 上進行篩選，請將 `claude-code-desktop` 新增至篩選條件，以同時擷取來自本機 Code 標籤工作階段的遙測資料。

## ROI 測量資源

如需有關測量 Claude Code 投資回報率的綜合指南，包括遙測設定、成本分析、生產力指標和自動化報告，請參閱 [Claude Code ROI 測量指南](https://github.com/anthropics/claude-code-monitoring-guide)。此儲存庫提供現成可用的 Docker Compose 配置、Prometheus 和 OpenTelemetry 設定，以及用於產生與 Linear 等工具整合的生產力報告的範本。

## 安全性和隱私

* OpenTelemetry 匯出到您的後端是選擇加入的，需要明確配置。如需了解 Anthropic 的獨立營運遙測以及如何停用它，請參閱[資料使用](https://code.claude.com/docs/zh-TW/data-usage.md#telemetry-services)
* 原始檔案內容和程式碼片段不包含在指標或事件中。追蹤跨度是單獨的資料路徑：請參閱下面的 `OTEL_LOG_TOOL_CONTENT` 項目
* 透過 OAuth 驗證時，`user.email` 包含在遙測屬性中，僅傳送到您配置的 OTel 端點，絕不會傳送到 Anthropic。如果這對您的組織是個問題，請與您的遙測後端合作以篩選或編輯此欄位
* 預設不收集使用者提示詞內容。僅記錄提示詞長度。若要包含提示詞內容，請設定 `OTEL_LOG_USER_PROMPTS=1`。啟用時：
  * `user_prompt` 事件在兩個屬性中帶有提示詞文字：`prompt` 和 [`prompt_text`](#user-prompt-event)。如果您在收集器中依屬性名稱捨棄或遮蔽事件的提示詞文字，請在規則中列出這兩個屬性

    此 OpenTelemetry Collector `attributes` 處理器會在列出它的管線中刪除這兩個屬性：

    ```yaml theme={null}
    processors:
      attributes/drop-prompt-text:
        actions:
          - key: prompt
            action: delete
          - key: prompt_text
            action: delete
    ```

  * 開啟[追蹤](#traces-beta)時，`claude_code.interaction` 跨度會在其 `user_prompt` 屬性中帶有提示詞文字

  * 在詳細的測試版追蹤下，跨度也會帶有每個請求所傳送的新使用者訊息、工具結果和系統提醒、系統提示詞文字，以及模型輸出。[詳細測試版追蹤下的內容屬性](#new-context-gates)列出了每個屬性。`claude_code.system_prompt` 事件帶有完整的系統提示詞
* 助理回應文字預設不收集。僅記錄回應長度。若要包含回應文字，請設定 `OTEL_LOG_ASSISTANT_RESPONSES=1`。如同 Claude Code 的所有 OpenTelemetry 資料，回應文字僅傳送到您設定的 OTel 端點，絕不會傳送到 Anthropic。當此變數未設定時，`OTEL_LOG_USER_PROMPTS` 會用作備援，因此如果您想要事件中有提示詞內容而不要回應內容，請設定 `OTEL_LOG_ASSISTANT_RESPONSES=0`。在詳細的測試版追蹤下，`claude_code.llm_request` 跨度仍會在 [`response.model_output`](#new-context-gates) 中帶有模型輸出，該屬性遵循 `OTEL_LOG_USER_PROMPTS` 而非此變數
* 工具輸入引數和參數預設不記錄。若要包含它們，請設定 `OTEL_LOG_TOOL_DETAILS=1`。針對 Claude Desktop 的內建伺服器，在 Claude Desktop 擁有的工作階段中，`tool_decision` 和 `tool_result` 帶有 `mcp_server_name`/`mcp_tool_name` 配對，即主機撰寫的名稱而非引數內容，即使旗標關閉也是如此。此資料僅傳送到您設定的 OTEL 端點，絕不會傳送到 Anthropic。引數仍可能包含敏感值，因此請根據需要設定您的遙測後端以篩選或編輯這些屬性。啟用時：
  * `tool_result` 和 `tool_decision` 事件包含 `tool_parameters` 屬性，其中包含 Bash 命令、MCP 伺服器和工具名稱以及 skill 名稱。`full_command` 等欄位未截斷地發出
  * `tool_result` 事件另外包含 `tool_input` 屬性，其中包含檔案路徑、URL、搜尋模式和其他引數。超過 512 個字元的個別值會被截斷，總計上限約為 4 K 字元
  * `user_prompt` 事件包含自訂、外掛和 MCP 命令的逐字 `command_name`
  * [成本和 token 計數器](#cost-counter)以及 `api_request`、`api_error` 和 `api_refusal` 事件在其歸因屬性中帶有真實的 agent、skill、外掛和 MCP 伺服器和工具名稱
  * `claude_code.tool` 跨度帶有輸入衍生屬性，例如 `file_path`。在詳細的測試版追蹤下，它還會帶有 [`tool_input`](#new-context-gates) 屬性
* 工具內容預設不在追蹤跨度中記錄。若要包含它，請設定 `OTEL_LOG_TOOL_CONTENT=1`。`claude_code.tool` 跨度隨後帶有 [`tool.output` 跨度事件](#tool-output-span-event)，其中包含原始檔案內容、Bash 命令輸出，以及 MCP 工具、WebFetch 和 WebSearch 傳回的內容，在內容限制（預設 60 KB）處按屬性截斷。來自 MCP 工具、WebFetch 和 WebSearch 的結果需要 Claude Code v2.1.283 或更新版本。工具內容也透過 [`new_context` 到達跨度，其控制因跨度而異](#new-context-gates)。根據需要配置您的遙測後端以篩選或編輯這些屬性
* 原始 Anthropic Messages API 請求和回應主體預設不記錄。若要包含它們，請在您的 shell、使用者設定或受管設定中設定 `OTEL_LOG_RAW_API_BODIES`。在[專案和本機設定](https://code.claude.com/docs/zh-TW/settings-reference.md#variables-claude-code-ignores-in-env)中會被忽略。主體包含完整的對話歷史記錄，包括系統提示、每個先前的使用者和助手輪次以及工具結果，因此啟用此選項意味著同意其他 `OTEL_LOG_*` 內容旗標會揭露的所有內容。Claude Code 始終從這些主體中編輯 Claude 的擴展思考內容，無論其他設定如何。您設定的值決定了 Claude Code 如何傳遞主體：
  * 使用 `=1` 時，Claude Code 為每個 API 呼叫發出 `api_request_body` 和 `api_response_body` 日誌事件。事件的 `body` 屬性帶有 JSON 序列化的承載，在內容限制（預設 60 KB）處截斷
  * 使用 `=file:<dir>` 時，Claude Code 將未截斷的主體寫入該目錄下的 `.request.json` 和 `.response.json` 檔案，事件帶有 `body_ref` 路徑而不是內聯主體。使用日誌收集器或邊車傳送目錄，而不是透過遙測流

    對於每個成功的回應，Claude Code 也會在該目錄中的 `index.jsonl` 附加一行，將回應檔案連結到產生它的請求檔案以及它成為的文字記錄訊息。每一行不包含任何訊息內容，[API 回應主體事件](#api-response-body-event)部分列出其欄位。索引檔案需要 Claude Code v2.1.274 或更新版本

## 在 Amazon Bedrock 上監控 Claude Code

如需 Amazon Bedrock 上 Claude Code 使用情況監控的詳細指南，請參閱 [Claude Code 監控實作 (Amazon Bedrock)](https://github.com/aws-solutions-library-samples/guidance-for-claude-code-with-amazon-bedrock/blob/main/assets/docs/MONITORING.md)。

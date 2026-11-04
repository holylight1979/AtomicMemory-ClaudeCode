<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits | lastmod: 2026-10-25 | section: Administration / Gateways -->
> 來源：https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits（官方 zh-TW，lastmod 2026-10-25）｜分類：Administration › Gateways｜EN 摘要：Cap each developer's spend through the Claude apps gateway by day, week, or month. Set limits with an Admin API and the gateway enforces them live on every request.

# Claude 應用程式閘道支出限制

> 透過 Claude 應用程式閘道限制每位開發人員的每日、每週或每月支出。使用管理員 API 設定限制，閘道會在每個請求上即時執行這些限制。

支出限制會限制每位開發人員在指定的一天、一週或一個月內透過您的 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 可以花費的金額。當開發人員超過其限制時，閘道會在他們的下一個請求上返回 `429`，並在該期間重置或管理員提高限制之前阻止他們。使用支出限制為每位開發人員、群組或整個組織設定共享認證的上限。

根據預設，Claude 應用程式閘道會透過一個共享的上游認證轉發所有推論，因此您的提供商的帳單會將所有內容歸屬於該認證，而不是個別開發人員。在 Amazon Bedrock 上，[按開發人員的 AWS 成本歸屬](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#per-developer-aws-cost-attribution) 會改變這一點。沒有按開發人員的限制，一個失控的代理程式群隊可能會花費組織的整個承諾。支出限制是閘道在該共享帳單之上的按開發人員檢視和斷路器。

## 設定上限

配置了 [`admin:`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin) 區塊在 `gateway.yaml` 中後，閘道會在 `/v1/organizations/spend_limits` 提供管理員 API，並在每個推論請求上即時執行上限。上限本身是透過該 API 設定的，而不是在 `gateway.yaml` 中；每個 `POST /v1/organizations/spend_limits` 請求會從 `{scope, amount, period}` 建立或替換一個上限。該 API 鏡像了 Anthropic 公開 [Admin API](https://platform.claude.com/docs/en/manage-claude/admin-api) 支出限制端點的線路形狀，因此針對該合約編寫的 HTTP 用戶端可以透過變更其基礎 URL 來針對閘道。

此請求為每位開發人員設定組織範圍的預設值，每月 \$500：

```bash theme={null}
curl -sS https://claude-gateway.internal.example.com/v1/organizations/spend_limits \
  -H "x-api-key: $GATEWAY_ADMIN_WRITE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": {"type": "organization"}, "amount": "50000", "period": "monthly"}'
```

此請求在 `contractors` 群組的每位成員上分層設定更嚴格的每日 \$100 上限：

```bash theme={null}
curl -sS https://claude-gateway.internal.example.com/v1/organizations/spend_limits \
  -H "x-api-key: $GATEWAY_ADMIN_WRITE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": {"type": "rbac_group", "rbac_group_id": "contractors"}, "amount": "10000", "period": "daily"}'
```

| 欄位 | 值 | 說明 |
| - | - | - |
| `scope.type` | `user`、`rbac_group`、`organization` | `user` 透過其 OpenID Connect (OIDC) `sub`（您的身份提供商指派的穩定使用者 ID）針對一位開發人員；將其作為 `scope.user_id` 傳遞。`rbac_group` 透過名稱針對 [IdP 群組](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#managed)；將其作為 `scope.rbac_group_id` 傳遞。`organization` 是組織範圍的預設值。閘道接受全部三種；Anthropic 的公開 `POST` 目前僅限使用者。 |
| `amount` | USD 美分的整數字串，或 `null` | `null` 表示無限制。`"0"` 是零上限，會阻止每個請求。 |
| `period` | `daily`、`weekly`、`monthly` | 一個範圍可以為每個期間保持一個上限，每個都獨立執行：如果開發人員超過其中任何一個，就會被阻止。 |

群組或組織上限是每位成員繼承的按座位預設值，而不是共享池。每個期間，開發人員的有效上限按此順序解析：按使用者覆蓋、其群組上限中最嚴格的、組織預設值，然後無限制。[`admin.group_limit_mode: max`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin) 會將多群組平局決勝改為最寬鬆的。

### 向管理員 API 進行身份驗證

傳送以下其中之一：

* 與 [`admin.write_keys`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin) 中的金鑰相符的 `x-api-key` 標頭以獲得完全存取權限，或 `admin.read_keys` 以獲得僅 `GET` 存取權限。每個金鑰都帶有一個 `id`，在稽核日誌中顯示為 `admin-key:<id>`，因此為 Terraform、CI 和每個自動化提供各自的金鑰。
* 其 `groups` 聲明包含 [`admin.admin_groups`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin) 之一的閘道持有人令牌。這是完全存取權限，稽核為 `oidc:<sub>`，因此對人類管理員更好。

## 執行方式

在每個 `/v1/messages` 請求上，閘道在一個 Postgres 查詢中查詢開發人員的上限和期間至今的支出。超過任何上限的開發人員會收到 `429`，其中 `error.type: billing_error` 和標頭 `x-should-retry: false`。

訊息會命名期間和重設時間，例如 `spend limit reached (daily; resets 2026-08-08 00:00 UTC)`，後面跟著您的 [`admin.blocked_message`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin)（如果已設定）。當開發人員同時超過多個上限時，訊息會命名最後重設的上限。回應也會攜帶 `retry-after` 標頭，其中包含距離該重設的剩餘秒數。在閘道伺服器上的 v2.1.225 之前，訊息是 `spend limit reached`，沒有期間、重設時間或 `retry-after` 標頭。

在 v2.1.227 或更新版本上，`<public_url>/protocol` 的協議參考也會列出確切的使用量限制回應標頭和 `429` 本文。

上限在 UTC 日曆邊界重設：每天在 00:00 UTC、每週星期一和每月的第一天。閘道永遠不會阻止 `/v1/messages/count_tokens`，因為令牌計數是免費的。

### 請求如何定價

在每個回應之後，使用量計量器讀取令牌計數，並將成本新增到每日、每週和每月計數器。它永遠不會觸及傳送給用戶端的位元組，因此計量失敗無法破壞回應。這些金額是美元估計值，是斷路器而不是發票；如需計費，請根據您提供商的使用情況報告進行協調。

計量器按此順序為每個請求選擇費率：

1. 為提供請求的上游提供的相符 [`pricing.overrides`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#pricing) 列。需要 v2.1.227 或更新版本。
2. 上游模型 ID 的清單價格，即閘道傳送給提供商的字串，當 Claude Code 成本表識別它時。該表接受 Anthropic、Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry ID 形式。
3. 您對應到該上游 ID 的 [`models[].id`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#models) 的清單價格，適用於不包含模型名稱的上游字串，例如 Amazon Bedrock 應用程式推論設定檔 ARN 或 Microsoft Foundry 部署名稱。需要 v2.1.218 或更新版本。
4. 未知模型層級，每百萬輸入/輸出令牌 \$5/\$25，因此計量器無法識別的 ID 永遠不會免費。閘道在啟動時和執行時每個 ID 一次警告當它使用此層級時。

無論適用哪個費率，計量器隨後將金額乘以 [`pricing.multiplier`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#pricing)，預設值為 `1`。

用戶端中止也會被計費。當串流在沒有上游最終使用量框架的情況下結束時，計量器會計費約每輸出令牌四個字元的下限估計，用於已傳送給用戶端的文字，因此提前中止請求不會規避上限。

#### 長提示詞費率

[Claude Haiku 5.5](https://platform.claude.com/docs/en/models/haiku-5-5/overview) 的清單價格[對超過 token 門檻的提示詞採用較高費率](https://code.claude.com/docs/zh-TW/model-config.md#haiku-5-5-context-window-and-pricing)。當 Haiku 5.5 處理提示詞超過該門檻的請求時，執行 Claude Code v2.1.293 或更新版本的閘道伺服器會以該費率為整個請求定價。計量器會將輸入 token、快取讀取和快取寫入計入該門檻。

如果您的某個 `pricing.overrides` 列與請求相符，則無論提示詞長度為何，都會套用該列的費率。

### Postgres 可用性

預檢查使用兩秒超時查詢 Postgres。如果存儲無法到達或超時，執行預設會開放失敗：請求繼續進行，閘道記錄警告，回應不攜帶 `anthropic-ratelimit-unified-*` 標頭。設定 [`enforcement.fail_closed_on_error: true`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#enforcement) 改為關閉失敗，這會返回相同的 `429 billing_error`，但訊息為 `spend limit unavailable`，沒有期間、重設時間或 `retry-after` 標頭。開放失敗可防止存儲中斷成為推論中斷；關閉失敗保證沒有無計量支出。

開放失敗只有在您的負載平衡器或協調器仍然將流量路由到閘道時才有幫助。請參閱[中斷行為](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#outage-behavior)以了解 `store.readiness_grace_seconds`，它可以讓副本在短暫中斷期間通過其就緒檢查。

### Claude Code 中的使用量警告

當開發人員接近其上限時，Claude Code 會發出警告：一旦使用率超過 75%，再次超過其最常消耗上限的 95%。當閘道阻止請求時，Claude Code 會按原樣顯示閘道的 `429` 訊息，包括您的 `admin.blocked_message`。它也會在 `/usage` 中顯示上限，並將其傳遞給開發人員的[狀態列](https://code.claude.com/docs/zh-TW/statusline.md#spend-limit-fields)指令碼。

每種顯示都需要開發人員機器上和閘道伺服器上的最低 Claude Code 版本：

| 開發人員看到的內容 | 開發人員的機器 | 閘道伺服器 |
| :- | :- | :- |
| 在 75% 和 95% 時的使用量警告 | v2.1.225 或更新版本 | v2.1.225 或更新版本 |
| `/usage` 中的 **Spend limit** 列，其中包含已使用的上限百分比及其重設時間，以及狀態列輸入中的 `rate_limits.spend_limit` 物件 | v2.1.251 或更新版本 | v2.1.225 或更新版本 |
| **Spend limit** 列中以美元表示的估計支出和上限，例如「\$271.40 / \$500.00 spent this month」，以及狀態列輸入中的相同金額加上上限的期間 | v2.1.284 或更新版本 | v2.1.284 或更新版本 |

警告和百分比來自 `anthropic-ratelimit-unified-*` 標頭，閘道會將這些標頭新增到具有上限的開發人員的每個成功 `/v1/messages` 回應中。標頭始終描述開發人員自己的上限：閘道會移除上游提供商的速率限制標頭（描述您的共享配額），並永遠不會轉發它們。

開發人員看到的支出是閘道自己的[估計值](#how-requests-are-priced)，與其用來執行上限的數字相同，而不是您提供商帳單上的金額。Claude Code 會透過對閘道的另一個請求讀取美元金額；即使您在開發人員的機器上設定了 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`，Claude Code 仍會傳送該請求。在 v2.1.295 之前，設定該變數時 Claude Code 會略過該請求，`/usage` 和狀態列只會顯示百分比和重設日期，不含美元金額。

## 管理員 API 參考

以下端點在 `/v1/organizations/spend_limits` 下提供。

| 方法和路徑 | 說明 |
| - | - |
| `GET /v1/organizations/spend_limits` | 列出已配置的上限，可選擇性地篩選到 `organization`、`rbac_group` 或 `user` 的一個 `scope_type`。查詢：`?limit=&after_id=&before_id=&scope_type=`。 |
| `POST /v1/organizations/spend_limits` | 為 `{scope, period}` 建立或替換上限。 |
| `GET /v1/organizations/spend_limits/{id}` | 透過其 `spl_` 前綴 ID 擷取一個上限。 |
| `DELETE /v1/organizations/spend_limits/{id}` | 刪除一個上限。返回 `{type: "spend_limit_deleted", id}`。 |
| `GET /v1/organizations/spend_limits/effective` | 每個主體每個期間的已解析上限和至今支出。 |
| `GET /v1/organizations/spend_limits/audit` | 管理員變更軌跡，最新優先。查詢：`?limit=&after_id=`。 |

慣例鏡像 Anthropic 的管理員 API：

* 每個物件上的 `type`
* `spl_` 前綴 ID
* 金額為 USD 美分的整數字串；`POST` 拒絕任何其他 `currency`，返回 `400`
* `{type: "error", error: {type, message}, request_id}` 錯誤信封
* 每個管理員回應上的 `request-id` 回應標頭，成功或錯誤；錯誤本文也將其作為 `request_id` 攜帶

每個變更在同一交易中向 `admin_audit` 寫入前/後行，歸屬於 `admin-key:<id>` 或 `oidc:<sub>`。

閘道僅提供支出限制端點。其他管理員 API 表面（例如 `spend_limit_increase_requests` 佇列）不是閘道管理員 API 的一部分。

### `/effective`

`GET /v1/organizations/spend_limits/effective` 返回 Anthropic 的 `SpendSummary` 架構：每行是一個主體的一個期間，具有已解析的上限、期間至今的支出和一個 `actor` 物件。閘道特定的差異：

* `user_id` 是 OIDC `sub`。
* `actor.name` 和 `actor.email_address` 為 `null`，直到主體透過閘道的第一個推論請求。閘道沒有使用者目錄；它從每個使用者自己的工作階段 JWT 記錄最後看到的值。
* 每行也帶有一個 `groups` 陣列，主體最後看到的 IdP 群組。這是一個閘道擴充，因此管理員 UI 可以顯示適用的每個上限層級；Anthropic 形狀的用戶端會忽略它。
* 沒有 `user_ids[]` 篩選，它列出有記錄支出的主體，因為閘道無法列舉所有組織成員。

群組來源的上限根據那些最後看到的群組解析，使用與執行相同的 `group_limit_mode` 平局決勝，因此檢視器顯示實際適用的上限。

| 查詢參數 | 說明 |
| - | - |
| `user_ids[]` | 可重複。按 OIDC `sub` 篩選到特定主體。 |
| `period[]` | 可重複。篩選到 `daily`、`weekly` 或 `monthly` 行。 |
| `sort` | `spend_desc` 首先列出最高支出者。需要恰好一個 `period[]`。 |
| `q` | 不區分大小寫的子字串篩選，涵蓋 OIDC `sub`、最後看到的電子郵件和最後看到的顯示名稱。 |
| `limit` / `page` | 頁面大小（1–1000，預設 20）和前一個回應的 `next_page` 中的不透明游標。 |

> [!WARNING]
>
> `q=` 和 `user_ids[]=` 乘坐 GET 查詢字串，因此任何前置代理或負載平衡器都會在其存取日誌中擷取它們。如果您的 PII 日誌原則很嚴格，請在那裡清理這些參數。

### `/audit`

返回支出限制變更軌跡：誰變更了哪個上限，具有前/後快照，最新優先。`has_more` 是精確的。此端點遵循本地管理員 API 慣例，而不是第一方線路形狀。

### 分頁

原始列表按 `after_id` 和 `before_id` 分頁，它們是互斥的 `spl_…` ID；結果按建立排序，`has_more` 反映遍歷方向。`/effective` 按傳回的不透明 `next_page` 令牌分頁，作為 `?page=` 傳遞，主體按升序排序，因此在記錄支出時頁面保持穩定。`limit` 在兩者上都是 1–1000，預設 20，在 `/audit` 上按 `after_id` 分頁，即前一頁上最後一個事件的數值 `id`，其 `limit` 預設為 100。

## 資料生命週期

閘道保持四個支出相關表；每小時掃描執行保留視窗：

| 表格 | 內容 | 保留 |
| - | - | - |
| `spend` | 按主體期間至今計數器（美分） | [`admin.spend_retention_months`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin)，預設 13 |
| `spend_limits` | 已配置的上限 | 直到透過 API 刪除 |
| `admin_audit` | 變更軌跡 | [`admin.audit_retention_days`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin)，預設 365 |
| `principal_emails` | 每個主體最後看到的電子郵件、顯示名稱和 IdP 群組。包含 PII。 | [`admin.identity_retention_days`](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin) 自上次活動起，預設 90 |

當開發人員離開時，透過 `DELETE /v1/organizations/spend_limits/{id}` 刪除任何按使用者上限；其支出和身份行按上述保留視窗老化。若要立即清除一個人，用於離職或資料主體存取請求 (DSAR)，直接針對閘道資料庫執行 `DELETE FROM principal_emails WHERE principal = '<sub>'`。這會移除唯一保持其電子郵件、名稱和群組的表格。`spend` 和 `admin_audit` 行僅參考偽匿名 OIDC `sub`，並按其自己的視窗老化。

## 相關

* [`admin` 和 `enforcement` 配置](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config#admin)：啟用管理員 API 和調整保留
* [部署指南](https://code.claude.com/docs/zh-TW/claude-apps-gateway-deploy.md#postgres)：Postgres 架構和備份指導

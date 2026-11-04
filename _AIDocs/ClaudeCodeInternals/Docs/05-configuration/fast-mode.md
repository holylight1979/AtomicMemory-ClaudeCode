<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/fast-mode | lastmod: 2026-11-02 | section: Configuration / Model and responses -->
> 來源：https://code.claude.com/docs/zh-TW/fast-mode（官方 zh-TW，lastmod 2026-11-02）｜分類：Configuration › Model and responses｜EN 摘要：Get faster Opus responses in Claude Code by toggling fast mode.

# 使用快速模式加快回應速度

> 在 Claude Code 中切換快速模式，以獲得更快的 Opus 回應。

> [!NOTE]
>
> Claude Opus 5.5 的快速模式已可使用，而 Claude Opus 5 和 Claude Opus 4.8 的快速模式則處於[研究預覽](#research-preview)階段。

快速模式是 Claude Opus 的高速配置，使模型速度提升最高 2.5 倍，但每個 token 的成本更高。當您需要速度進行互動式工作（如快速迭代或實時調試）時，使用 `/fast` 切換開啟，當成本比延遲更重要時，切換關閉。

快速模式不是不同的模型。它使用 Claude Opus 搭配不同的 API 配置，優先考慮速度而非成本效率。您獲得相同的品質和功能，只是回應速度更快。快速模式在 Opus 5.5、Opus 5 和 Opus 4.8 上受支援。它在 Sonnet、Haiku 或其他模型上不可用。

> [!WARNING]
>
> Opus 4.8 的快速模式已於 2026 年 10 月 30 日棄用，並將於 2026 年 11 月 30 日移除。如果在該日期之後，您的模型仍為 Opus 4.8 且快速模式為開啟狀態，API 將拒絕您的請求。請在該日期之前，切換至 Opus 5.5 或在您的工作階段中關閉快速模式：
>
> * **若要保留快速模式**：使用 [`/model`](https://code.claude.com/docs/zh-TW/model-config#setting-your-model) 切換至 [Opus 5.5](https://code.claude.com/docs/zh-TW/model-config.md#model-aliases)，這需要 Claude Code v2.1.280 或更新版本。切換後快速模式會保持開啟。如果新的工作階段仍以 Opus 4.8 啟動，請參閱[新的工作階段以不同於您所選的模型啟動](https://code.claude.com/docs/zh-TW/model-config.md#a-new-session-starts-on-a-different-model-than-you-picked)。
> * **若要以標準速度繼續使用 Opus 4.8**：執行 [`/fast off`](https://code.claude.com/docs/zh-TW/commands)

Opus 4.7 不支援快速模式，因此切換至它會關閉快速模式。Opus 4.7 的快速模式已於 2026 年 6 月 25 日棄用，並於 2026 年 7 月 24 日移除。

需要了解的事項：

* 使用 `/fast` 在 Claude Code CLI 中切換快速模式。[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)在選定的模型支援快速模式時提供**切換快速模式**命令。Claude Code 將該切換儲存到您的 [`fastMode` 設定](#toggle-fast-mode)。
* 快速模式定價在 Opus 5.5 上為 $8/$40 MTok 輸入/輸出，在 Opus 5 和 Opus 4.8 上為 $10/$50 MTok 輸入/輸出。
* 適用於訂閱方案（Pro/Max/Ultra/Team/Enterprise）上的 Claude Code 使用者和 Claude Console。Team 和 Enterprise 組織需要擁有者先啟用它，Console 組織則需要先佈建存取權限，才能搭配 Opus 5 或 Opus 4.8 使用。[需求](#requirements)說明了這兩者。
* 對於訂閱方案（Pro/Max/Ultra/Team/Enterprise）上的 Claude Code 使用者，快速模式僅透過用量點數提供，不包含在訂閱速率限制中。

## 切換快速模式

在 CLI 中，可透過以下任一方式切換快速模式：

* 執行 `/fast`，按 Space 切換開啟或關閉，然後按 Enter 確認
* 在您的[使用者設定檔](https://code.claude.com/docs/zh-TW/settings.md)中設定 `"fastMode": true`

預設情況下，在互動式工作階段中開啟的快速模式會跨工作階段保留。您可以將快速模式設定為在每個工作階段重設。詳情請參閱[要求每個工作階段選擇加入](#require-per-session-opt-in)。

在[雲端工作階段](#use-fast-mode-in-cloud-sessions)之外，於使用 `-p` 旗標的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，`/fast` 僅在其 [`--settings`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 值中啟用快速模式所啟動的工作階段中有效，例如 `claude -p --settings '{"fastMode": true}'`；此時切換僅套用於該工作階段，不會儲存為您的預設值。`-p` 形式需要 Claude Code v2.1.205 或更新版本。在其他非互動模式情況下，該命令會回報快速模式無法使用。

您可以在 Claude 工作時執行 `/fast`，Claude Code 會切換快速模式，而不需等待回合結束。Claude Code 會以原本的速度完成正在執行的回合，因此速度變更會從您的下一個回合開始生效。如果您目前的模型不支援快速模式，開啟快速模式也會切換您的模型，且 Claude Code 會在該回合中從下一個請求開始使用新模型。

為了獲得最佳的成本效益，請在工作階段開始時啟用快速模式，而非在對話中途切換。詳情請參閱[了解成本權衡](#understand-the-cost-tradeoff)。

當您啟用快速模式時：

* 如果您目前的模型不支援快速模式，Claude Code 會切換至 Opus
* 您會看到確認訊息："Fast mode ON"
* 快速模式啟用期間，提示詞旁會出現一個小型 `↯` 圖示
* 隨時再次執行 `/fast` 即可檢查快速模式是開啟還是關閉

在 Claude Code v2.1.280 及更新版本中，Opus 5.5 是快速模式的預設模型。在 v2.1.280 之前，從 v2.1.219 起快速模式預設使用 Opus 5。

當您再次使用 `/fast` 停用快速模式時，您會繼續使用 Opus。若要切換至其他模型，請使用 `/model`。

### 在快速模式開啟時切換模型

快速模式會雙向跟隨您的模型切換：

* **切換離開**：當您切換至不支援快速模式的模型時，Claude Code 會關閉快速模式。這包括 Opus 4.7；在 v2.1.221 之前，切換至 Opus 4.7 後快速模式仍保持開啟，且 API 會拒絕這些請求。
* **切換回來**：當您儲存的快速模式偏好設定為開啟時（即新工作階段預設採用的相同偏好設定），切換回受支援的 Opus 模型會再次開啟快速模式。對於已儲存偏好設定為關閉的工作階段，模型切換絕不會開啟快速模式；若已設定[每個工作階段選擇加入](#require-per-session-opt-in)，切換回來也不會開啟快速模式；請執行 `/fast` 重新啟用。

每當模型切換開啟或關閉快速模式時，Claude Code 都會顯示 `Fast mode ON` 或 `Fast mode OFF` 確認訊息，且快速模式開啟期間會出現 `↯` 圖示。無論您是使用 `/model`、使用 [`/config model=<model>`](https://code.claude.com/docs/zh-TW/settings)，還是從透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連線的裝置進行切換，皆是如此。

在模型切換、重新連線或[可用性檢查](#use-fast-mode-behind-proxies-and-llm-gateways)失敗後，Claude Code 會將工作階段的快速模式狀態重新傳送至透過 Remote Control 連線的裝置。

### 在雲端工作階段中使用快速模式

當您的帳戶可使用快速模式時，快速模式可在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中運作，無論該工作階段是在 Anthropic 管理的基礎架構上執行，還是在[自行託管的執行器](https://code.claude.com/docs/zh-TW/self-hosted-environments)上執行。工作階段的環境需要 Claude Code v2.1.271 或更新版本。

在工作階段中輸入 `/fast on` 即可開啟快速模式。它僅在該工作階段中保持開啟，不會儲存為您的預設值。[需求](#requirements)同樣適用於雲端工作階段。

在瀏覽器中的 [claude.ai/code](https://claude.ai/code)，您也可以從訊息方塊上的模型選單開啟或關閉快速模式。當您的方案包含快速模式且所選模型支援時，選單會顯示此開關。

## 了解成本權衡

快速模式的每個 token 定價高於標準 Opus：

| 模型 | 輸入 (MTok) | 輸出 (MTok) |
| - | - | - |
| Opus 5.5 | \$8 | \$40 |
| Opus 5 | \$10 | \$50 |
| Opus 4.8 | \$10 | \$50 |

快速模式定價在整個 1M token 上下文視窗中是固定的。如需與標準 Opus 費率進行比較，請參閱 [Claude 定價參考](https://platform.claude.com/docs/zh-TW/about-claude/pricing)。

當您在對話中首次啟用快速模式時，您需要為整個對話上下文支付完整的快速模式未快取輸入 token 價格。對話進行得越深入，這筆費用就越高，因此在對話開始時就啟用快速模式，這筆費用最低。快速模式與標準速度會保留[各自獨立的快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#turning-on-fast-mode)，因此之後每次切換時，都會再次以未快取方式讀取部分或全部對話內容。

### 查看快速模式支出出現的位置

您看到快速模式支出的位置取決於您如何登入，因此請先執行 [`/status`](https://code.claude.com/docs/zh-TW/commands) 來檢查。如果它顯示 `Login method` 列（例如 `Claude Max account`），表示您使用 Claude 訂閱登入。如果改為顯示 `API key` 列，您的請求將計費到 Claude Console 組織。

* **Pro、Max 和 Ultra**：您從用量點數中支付快速模式費用。前往 claude.ai 上的 [**設定 > 使用情況**](https://claude.ai/settings/usage)，其中 **用量點數** 部分顯示您本月在用量點數中花費了多少。該數字包括快速模式，但不會單獨列出。
* **Team 和 Enterprise**：您的組織從其使用額度中支付您的快速模式使用費用。若要查看您自己的使用額度支出，請執行 [`/usage`](https://code.claude.com/docs/zh-TW/costs#check-your-usage-credits-spend)。如需了解您的組織在何處查看該支出，請參閱 [Claude for Teams and Enterprise](https://code.claude.com/docs/zh-TW/costs.md#claude-for-teams-and-enterprise)。
* **Claude Console**：您的組織使用其 API 使用的其餘部分支付快速模式費用。在 Console [使用情況](https://platform.claude.com/usage) 和 [成本](https://platform.claude.com/cost) 頁面上，在 **分組依據** 選單中選擇 **Speed (research preview)** 以將快速模式與標準速度使用分開。只有當選定的日期範圍包括快速模式使用時，您才會看到該選項。

## 決定何時使用快速模式

快速模式最適合用於回應延遲比成本更重要的互動式工作：

* 快速迭代程式碼變更
* 實時調試工作階段
* 時間敏感的工作，有緊迫的截止日期

標準模式更適合：

* 速度不那麼重要的長期自主任務
* 批次處理或 CI/CD 管道
* 成本敏感的工作負載

### 快速模式與努力等級

快速模式和努力等級都會影響回應速度，但方式不同：

| 設定 | 效果 |
| - | - |
| **快速模式** | 相同的模型品質、更低的延遲、更高的成本 |
| **較低的努力等級** | 較少的思考時間、更快的回應、複雜任務上可能品質較低 |

您可以結合兩者：在直接任務上使用快速模式搭配較低的[努力等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)以獲得最大速度。

## 需求

快速模式需要以下所有條件：

* **僅限 Anthropic API 或訂閱**：快速模式可透過 Anthropic Console API 和使用用量點數的 Claude 訂閱方案取得。在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 AWS 上的 Claude Platform 上無法使用。Console 組織還必須[佈建快速模式存取](#enable-fast-mode-for-your-organization)，才能在 Opus 5 或 Opus 4.8 上使用它。
* **為訂閱方案開啟用量點數**：在 Pro、Max、Ultra、Team 或 Enterprise 方案上，您的帳戶必須開啟[用量點數](https://code.claude.com/docs/zh-TW/costs.md#add-usage-credits-to-your-subscription)，這允許超出您方案包含使用量的計費。在開啟之前，`/fast` 會報告「快速模式需要用量點數」。若要開啟它們，請依照您方案對應的步驟操作：
  * 在 Pro、Max 和 Ultra 上，在 claude.ai 上的 [**設定 > 使用量**](https://claude.ai/settings/usage) 的 **用量點數** 部分開啟它們，或執行 `/usage-credits` 以開啟該頁面。
  * 在 Team 和 Enterprise 上，具有計費存取權限的成員在 [**組織設定 > 使用量**](https://claude.ai/admin-settings/usage) 為組織開啟它們，沒有存取權限的成員執行 `/usage-credits` 以向組織的管理員發送請求。

> [!NOTE]
>
> 快速模式使用量直接從使用額度中扣除，即使您在方案上還有剩餘使用量。

* **付費 Console 組織**：Claude Console 帳戶不使用使用額度，您的組織按令牌為快速模式付費，與其餘 API 使用量一起。在 Console 的免費評估方案上，`/fast` 顯示「評估期間快速模式不可用。請購買額度。」若要清除它，請在您的 [Console 計費設定](https://platform.claude.com/settings/billing)中購買額度。

  在 Opus 5.5 上使用快速模式也取決於您組織的[使用層級](https://platform.claude.com/docs/en/api/rate-limits)。
* **Team 和 Enterprise 的擁有者啟用**：快速模式在預設情況下對 Team 和 Enterprise 組織停用。擁有者必須明確[啟用快速模式](#enable-fast-mode-for-your-organization)，使用者才能存取它。

> [!NOTE]
>
> 四個組織設定可以阻止使用 `/fast` 開啟快速模式：
>
> * **快速模式未啟用**：如果尚未為您的組織啟用快速模式，使用 `/fast` 開啟快速模式會顯示「快速模式已被您的組織停用。」
> * **快速模式被受管設定關閉**：如果您的組織部署[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)，設定 [`fastMode: false`](https://code.claude.com/docs/zh-TW/settings-reference#fastmode)，使用 `/fast` 開啟快速模式會顯示相同的「快速模式已被您的組織停用」訊息。
> * **需要每個工作階段的選擇加入**：設定 [`fastModePerSessionOptIn: true`](#require-per-session-opt-in) 的受管設定會在除了互動式終端工作階段以外的所有地方拒絕 `/fast on`，顯示相同的訊息。
> * **快速模式模型不允許**：如果您組織的 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 允許清單排除快速模式 Opus 模型，開啟它會被拒絕，顯示「不在您組織的允許模型中」。在已在支援快速模式的允許 Opus 模型上執行的工作階段中，`/fast` 改為在您目前的模型上啟用快速模式，而不是切換模型。

### 為您的組織啟用快速模式

您啟用快速模式的位置取決於您的組織使用哪個產品：

* **Console**（API 客戶）：管理員在 [Claude Code 偏好設定](https://platform.claude.com/claude-code/preferences)中啟用它
* **Claude AI**（Team 和 Enterprise）：擁有者在 [**組織設定 > Claude Code**](https://claude.ai/admin-settings/claude-code) 啟用它

使用 Claude Opus 5 或 Claude Opus 4.8 的 Console 組織還需要佈建的存取權，如 [Claude API 上的快速模式](https://platform.claude.com/docs/en/build-with-claude/fast-mode)中所述。沒有該存取權，這些模型上的快速模式請求會觸及[快速模式速率限制](#handle-rate-limits)，並回退到標準速度，直到佈建存取權為止。

另一個完全停用快速模式的選項是設定 `CLAUDE_CODE_DISABLE_FAST_MODE=1`。請參閱[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)。

### 在代理和 LLM 閘道後面使用快速模式

在提供快速模式之前，Claude Code 會透過直接向 `api.anthropic.com` 的請求檢查您組織的快速模式可用性。該檢查不遵循 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/llm-gateway-connect#set-the-base-url-and-credential)，因此在將 Claude 流量路由透過 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)並阻止直接出口到 `api.anthropic.com` 的網路上，即使推理請求有效，檢查也會失敗。該檢查確實使用已設定的 [HTTP 代理](https://code.claude.com/docs/zh-TW/network-config.md#proxy-configuration)，因此網路阻止只在 `api.anthropic.com` 即使透過代理也無法到達的地方才會使檢查失敗。

如果您的組織已啟用快速模式，但 `/fast` 顯示並非如此，請在下列情況中找到它顯示的訊息。

#### Fast mode unavailable due to network connectivity issues

可用性檢查失敗（例如因為您的網路阻止 `api.anthropic.com`），請求會以標準速度執行。過去成功的檢查會從其快取結果繼續運作，因此被阻止的檢查主要影響新安裝。

若要復原快速模式，請將直接出口到 `api.anthropic.com` 加入允許清單，或設定 `CLAUDE_CODE_SKIP_FAST_MODE_NETWORK_ERRORS=1`，這會將失敗的檢查視為可用，並仍然遵守「已被您的組織停用」的回應。

#### Fast mode is currently unavailable

在閘道後面，請檢查下列設定，在這些設定中 Claude Code 不會發送可用性檢查，且沒有先前成功的檢查快取：

* 您將 `ANTHROPIC_BASE_URL` 指向您的閘道，並將 [`ANTHROPIC_API_KEY`](https://code.claude.com/docs/zh-TW/llm-gateway-connect#set-the-base-url-and-credential) 設定為閘道發行、但不符合 Anthropic API 金鑰格式的金鑰。
* 您設定了 [`CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`](https://code.claude.com/docs/zh-TW/env-vars)，因此 Claude Code 會跳過檢查。

若要在任一設定中復原快速模式，請設定 `CLAUDE_CODE_SKIP_FAST_MODE_NETWORK_ERRORS=1`。

#### Fast mode has been disabled by your organization

在閘道後面，即使您的組織已啟用快速模式，您也可能在下列任一設定中看到此訊息：

* 您僅使用 [`ANTHROPIC_AUTH_TOKEN`](https://code.claude.com/docs/zh-TW/llm-gateway-connect#set-the-base-url-and-credential) 進行驗證，沒有 claude.ai 登入、沒有 API 金鑰，也沒有快取的成功檢查。Claude Code 接著會將快速模式視為已被您的組織停用，而不發送請求。
* 代理伺服器攔截檢查並以自己的頁面回答，例如傳回 HTTP 200 阻止頁面的 TLS 檢查代理伺服器。Claude Code 會將該頁面讀取為表示您的組織已停用快速模式的回應。

在這兩種情況下，請設定 `CLAUDE_CODE_SKIP_FAST_MODE_ORG_CHECK=1`（這會完全跳過檢查），而不是 `CLAUDE_CODE_SKIP_FAST_MODE_NETWORK_ERRORS`（它不適用於任何一種情況）。

> [!NOTE]
>
> 跳過變數只會變更用戶端檢查。當您的組織已停用快速模式時，無論是否設定了這些變數，API 都會拒絕快速模式請求。Claude Code 接著會以標準速度重試請求，關閉快速模式，並且 `/fast` 會報告您的組織已停用快速模式。

### 需要每個工作階段的選擇加入

預設情況下，使用者在互動式工作階段中開啟的快速模式會在工作階段之間持續。若要變更此設定，請在任何[設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中將 `fastModePerSessionOptIn` 設定為 `true`，這會導致每個工作階段以快速模式關閉開始，並要求使用者使用 `/fast` 明確啟用它。[Team](https://claude.com/pricing?utm_source=claude_code\&utm_medium=docs\&utm_content=fast_mode_teams#team-&-enterprise) 或 [Enterprise](https://anthropic.com/contact-sales?utm_source=claude_code\&utm_medium=docs\&utm_content=fast_mode_enterprise) 方案上的擁有者可以透過[伺服器管理的設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md)在整個組織範圍內部署它。

```json theme={null}
{
  "fastModePerSessionOptIn": true
}
```

這對於在使用者執行多個並行工作階段的組織中控制成本很有用。使用者的快速模式偏好設定仍會被保存，因此移除此設定會復原預設的持續行為。

當受管設定設定該金鑰時，`/fast on` 只在互動式終端工作階段中有效。在其他所有地方，包括[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)、[VS Code 擴充功能](https://code.claude.com/docs/zh-TW/vs-code.md)和[雲端工作階段](#use-fast-mode-in-cloud-sessions)，它會被拒絕，顯示您的組織已停用快速模式的訊息。

## 處理速率限制

快速模式與標準 Opus 有不同的速率限制；對於 Console 組織，Claude Platform 的[速率限制](https://platform.claude.com/docs/en/api/rate-limits)頁面中有相關說明。當您達到快速模式速率限制時：

1. 快速模式自動回退到標準速度
2. `↯` 圖示變灰以指示冷卻
3. 您以標準速度和定價繼續工作
4. 冷卻期過期時，快速模式自動重新啟用

要手動禁用快速模式而不是等待冷卻，請再次執行 `/fast`。

如果您在工作階段中途用完使用額度，Claude Code 會在標準速度和定價下重試每個被拒絕的快速模式請求，因此您可以繼續工作，且沒有冷卻期。您看到拒絕的方式取決於工作階段類型：

* 在互動式工作階段中，Claude Code 會顯示「快速模式已禁用 · 使用額度已耗盡」通知，並在工作階段的其餘時間關閉快速模式。您儲存的快速模式偏好設定不會改變；執行 `/fast` 以重新開啟快速模式。
* 在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中使用 `--output-format stream-json`，以及透過 Agent SDK，Claude Code 會在訊息串流上以 `system` 訊息的形式發出相同的文字，子類型為 `notification`，在您用完使用額度時每個回合發出一次。快速模式保持開啟。需要 Claude Code v2.1.221 或更新版本。

## 研究預覽

Claude Opus 5 和 Claude Opus 4.8 的快速模式是研究預覽功能。這意味著：

* 該功能可能會根據反饋而改變
* 可用性和定價可能會改變
* 底層 API 配置可能會演變

透過您通常的 Anthropic 支援管道報告問題或反饋。

## 另請參閱

* [模型配置](https://code.claude.com/docs/zh-TW/model-config.md)：切換模型和調整努力等級
* [有效管理成本](https://code.claude.com/docs/zh-TW/costs.md)：追蹤 token 使用量並降低成本
* [狀態行配置](https://code.claude.com/docs/zh-TW/statusline.md)：顯示模型和上下文資訊

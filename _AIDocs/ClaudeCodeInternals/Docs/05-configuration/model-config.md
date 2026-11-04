<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/model-config | lastmod: 2026-11-03 | section: Configuration / Model and responses -->
> 來源：https://code.claude.com/docs/zh-TW/model-config（官方 zh-TW，lastmod 2026-11-03）｜分類：Configuration › Model and responses｜EN 摘要：Configure which model Claude Code uses, effort levels, extended context, and the auto-compact window

# 模型設定

> 設定 Claude Code 使用的模型、effort 等級、延伸上下文以及自動壓縮視窗

## 可用模型

對於 Claude Code 中的 `model` 設定，您可以設定以下任一項：

* **模型別名**
* **模型名稱**
  * Anthropic API：完整的 **[模型名稱](https://platform.claude.com/docs/en/about-claude/models/overview)**
  * Amazon Bedrock：推論設定檔 ARN
  * Microsoft Foundry：部署名稱
  * Google Cloud's Agent Platform：版本名稱

關於哪種模型和 effort 等級適合不同類型的工作，請參閱部落格上的 [Choosing a Claude model and effort level in Claude Code](https://claude.com/blog/claude-model-and-effort-level-in-claude-code)。

> [!NOTE]
>
> `ANTHROPIC_BASE_URL` 變更的是請求傳送的目的地，而非由哪個模型回應。若要透過 LLM 閘道路由 Claude，請參閱 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)。

### 模型別名

使用模型別名即可選擇模型設定，無需記住確切的版本號碼：

| 模型別名 | 行為 |
| - | - |
| **`default`** | 特殊值，會清除任何模型覆寫並還原為[您帳戶的執行階段預設值](#default-model-setting)。其本身並非模型別名 |
| **`best`** | 在您可使用 Fable 時，使用 [`fable` 別名解析到的](#fable-alias-resolution)模型，否則使用與 `opus` 相同的模型 |
| **`fable`** | 使用[您供應商的 Fable 模型](#fable-alias-resolution)處理最困難且執行時間最長的任務 |
| **`sonnet`** | 使用最新的 Sonnet 模型處理日常程式設計任務 |
| **`opus`** | 使用最新的 Opus 模型處理複雜的推理任務 |
| **`haiku`** | 使用快速且高效的 Haiku 模型處理簡單任務 |
| **`sonnet[1m]`** | 使用具有 [100 萬 token 上下文視窗](https://platform.claude.com/docs/en/build-with-claude/context-windows#context-window-sizes-by-model)的 Sonnet 進行長時間工作階段。當 `sonnet` 已解析為原生具備 1M 視窗的 Sonnet 5.5 或 Sonnet 5 時沒有作用 |
| **`opus[1m]`** | 使用具有 [100 萬 token 上下文視窗](https://platform.claude.com/docs/en/build-with-claude/context-windows#context-window-sizes-by-model)的 Opus 進行長時間工作階段。當 `opus` 已解析為原生具備 1M 視窗的 Opus 4.7 或更新版本時沒有作用 |
| **`opusplan`** | 特殊模式，在 plan mode 期間使用 `opus`，然後在執行時切換至 `sonnet` |

`opus`、`sonnet` 和 `haiku` 別名在 Anthropic API 上會解析為最新版本，在部分其他供應商上則會解析為較早的版本：

| 供應商 | `opus` | `sonnet` | `haiku` |
| :- | :- | :- | :- |
| Anthropic API | Opus 5.5 | Sonnet 5.5 | Haiku 5.5 |
| [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) | Opus 5.5 | Sonnet 4.6 | Haiku 4.5 |
| Amazon Bedrock、Google Cloud's Agent Platform | Opus 5.5 | Sonnet 4.5 | Haiku 4.5 |
| Microsoft Foundry | Opus 4.6 | Sonnet 4.5 | Haiku 4.5 |

除非您設定了 `ANTHROPIC_DEFAULT_FABLE_MODEL`，否則 `fable` 別名會解析為 Fable 5.1，但在 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段中例外，此時 `fable` 和 `best` 會解析為 Fable 5。

未設定為提供 `claude-fable-5-1` 的閘道會拒絕對該模型的請求。若要透過提供該模型的閘道使用 Fable 5.1，請使用 `/model claude-fable-5-1` 選擇它。

當 `opus` 或 `sonnet` 解析為較舊的模型時，您可以明確選擇完整模型名稱，或設定 `ANTHROPIC_DEFAULT_OPUS_MODEL` 或 `ANTHROPIC_DEFAULT_SONNET_MODEL` 來使用較新的模型。

較早的版本會將這些別名解析為較舊的模型。關於每個別名變更時的版本，請參閱[版本歷史](#version-history)。

別名會指向您供應商的建議版本，並隨時間更新。若要固定使用特定版本，請使用完整模型名稱，例如 `claude-opus-5-5`，或設定對應的環境變數，例如 `ANTHROPIC_DEFAULT_OPUS_MODEL`。

> [!NOTE]
>
> Sonnet 5.5 需要 Claude Code v2.1.284 或更新版本，Opus 5.5 需要 v2.1.280 或更新版本。如果從較舊版本對其中任一模型發出的請求失敗，請參閱 [Claude Code does not support this model](https://code.claude.com/docs/zh-TW/errors.md#claude-code-does-not-support-this-model)。使用 Haiku 5.5 時請使用 v2.1.293 或更新版本。執行 `claude update` 進行升級。

### 使用 Fable

[Claude Fable 5.1](https://platform.claude.com/docs/en/about-claude/models/overview) 和 Claude Fable 5 是 Claude Code 中能力最強的模型，適合無法一次完成的大型任務。它們能維持長時間的自主工作階段，在行動前先進行調查，並且比較小的模型更頻繁地驗證自己的工作。Fable 5.1 是較新的版本。

在任何方案或供應商上，這兩個 Fable 模型都不是帳戶類型的預設模型。請明確選擇其中之一：

* **Fable 5.1**：執行 `/model fable`，或以 `claude --model fable` 啟動。在 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段中，由於別名會解析為 Fable 5，請改為執行 `/model claude-fable-5-1`。
* **Fable 5**：透過模型 ID 選擇。在 Anthropic API 上，執行 `/model claude-fable-5` 或以 `claude --model claude-fable-5` 啟動。在其他供應商上，請使用您供應商的 Fable 5 模型 ID，或使用 `ANTHROPIC_DEFAULT_FABLE_MODEL` [固定它](#pin-models-for-third-party-deployments)。

如果您直接連線至 Anthropic API，且您的使用者設定將 `claude-fable-5` 或 `claude-fable-5[1m]` 保存為模型（例如因為您在 v2.1.257 之前於 `/model` 選擇器中選擇了 Fable），Claude Code 會在您首次執行 v2.1.257 或更新版本時，將該已儲存的值變更為 `fable` 或 `fable[1m]` 別名。啟動時的模型列會顯示一次 `(auto-updated)`。專案、本機或受管設定中的 `claude-fable-5` 值則維持不變。

被 Fable 模型的安全分類器標記的請求（最常見於網路安全和生物學領域）會觸發[自動模型備援](#automatic-model-fallback)。

若要充分發揮 Fable 的效益：

* **描述結果，而非步驟**：告訴它您想要的結果，讓它自行規劃路徑。若要讓它持續朝該結果努力，請[設定目標](https://code.claude.com/docs/zh-TW/goal.md)。
* **交給它模糊的問題**：根本原因調查、服務中斷除錯和架構決策，正是額外調查與驗證能帶來回報的地方。
* **省略驗證提醒**：它只需較少的提示就會驗證自己的工作，因此通常不需要提醒它測試或檢查。
* **給予更大的任務**：交給它您通常會拆分成多個部分的工作。它能維持長時間工作階段而不失去脈絡。

> [!NOTE]
>
> Fable 5.1 需要 Claude Code v2.1.257 或更新版本。如果從較舊版本對其發出的請求失敗，請參閱 [Claude Code does not support this model](https://code.claude.com/docs/zh-TW/errors.md#claude-code-does-not-support-this-model)。執行 `claude update` 進行升級。關於零資料保留下的可用性，請參閱 [ZDR 下的模型可用性](https://code.claude.com/docs/zh-TW/zero-data-retention.md#model-availability-under-zdr)。

在 Anthropic API 上，Fable 模型會出現在 `/model` 選擇器中，除非 [`availableModels`](#restrict-model-selection) 或[組織模型限制](#organization-model-restrictions)將其排除。當您的組織完全無法使用 Fable 時（例如在[零資料保留](https://code.claude.com/docs/zh-TW/zero-data-retention.md#model-availability-under-zdr)下），該列仍會以灰色顯示於選擇器中，並附上原因說明。

#### Fable 與用量點數

視您的方案和席位等級而定，Fable 的使用量可能會計入[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)，而非使用您方案內含的限額。在此情況下，`/model` 選擇器會在 Fable 列上顯示「Requires usage credits」。若要管理用量點數，請參閱[為您的訂閱新增用量點數](https://code.claude.com/docs/zh-TW/costs.md#add-usage-credits-to-your-subscription)。

在互動式工作階段中，Claude Code 可能會顯示 Fable 用量點數同意提示。採用組織計費的 Enterprise 方案成員不會看到此提示。您可以選擇使用用量點數繼續使用 Fable，或切換至您的預設模型。您也可以關閉此提示：

* 當您使用 `/model` 選擇 Fable 模型時，會保留目前的模型。
* 在工作階段進行中，Claude Code 會以您的預設模型繼續該回合。

在您選擇使用用量點數繼續使用 Fable 之後，Claude Code 不會再次顯示此提示。

在已連線 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 的工作階段、[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)或 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員的工作階段中，終端機前可能沒有人，因此 Claude Code 會將工作階段中的同意提示保留至 [`dialogExpiry`](https://code.claude.com/docs/zh-TW/settings-reference#dialogexpiry) 期限，預設為五分鐘。如果在期限前無人回應，Claude Code 會在不傳送請求的情況下結束該回合，並在逐字稿中加入通知，Remote Control 用戶端也會顯示該通知。您的模型選擇維持不變，Claude Code 會在您下一則訊息時再次請求同意。

提示等待期間您可以執行的操作取決於工作階段：

* 在已連線 Remote Control 或在隊員的工作階段中，於終端機按下任意鍵即可取消期限，Claude Code 會等待您的回應。
* 在背景工作階段中，請在期限前回應。
* 如果您在任何人於終端機輸入之前從遠端用戶端傳送新訊息，Claude Code 會以相同方式結束該回合，而您的新訊息會開始下一個回合。在有人於終端機輸入之後，Claude Code 會持續等待回應，並將您的新訊息排在其後。

在其他應用程式透過 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 託管的工作階段中，是否顯示提示由該應用程式決定。如果顯示提示且在相同的 [`dialogExpiry`](https://code.claude.com/docs/zh-TW/settings-reference#dialogexpiry) 期限前無人回應，Claude Code 會在不傳送請求的情況下結束該回合。

在使用 `-p` 旗標的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，以及在不顯示提示的 Agent SDK 應用程式中，Claude Code 永遠不會請求同意。當 Fable 請求會計入用量點數時，Claude Code 會直接計費而不詢問。

### 設定您的模型

您可以透過多種方式設定模型，以下依優先順序列出：

1. **工作階段期間**：使用 `/model <alias|name>` 立即切換，或執行不帶引數的 `/model` 開啟選擇器。請參閱 [Claude Code 何時會要求您確認切換](https://code.claude.com/docs/zh-TW/prompt-caching.md#switching-models)
2. **啟動時**：以 `claude --model <alias|name>` 啟動
3. **環境變數**：設定 `ANTHROPIC_MODEL=<alias|name>`
4. **設定**：在您的設定檔中使用 `model` 欄位永久設定
5. **[新工作階段的預設值](#set-a-default-model-for-new-sessions)**：設定 `ANTHROPIC_DEFAULT_MODEL=<alias|name>`

`/model` 會透過在您的使用者設定中寫入 `model` 欄位，將您的選擇儲存為新工作階段的預設值。在選擇器中：

* `Enter`：切換模型並儲存為您的預設值
* `s`：僅為此工作階段切換模型，並保持您的預設值不變。若要使用其他按鍵，請重新綁定 [`modelPicker:thisSessionOnly`](https://code.claude.com/docs/zh-TW/keybindings#model-picker-actions)

直接輸入 `/model <name>` 的行為與 `Enter` 相同。若要僅為此工作階段切換，請以 `/model` 開啟選擇器，並在該模型的列上按下 `s`。

在 Enterprise 方案中，當您以 claude.ai 帳戶登入並使用 `/model` 儲存預設值時，Claude Code 也會在該帳戶上記錄此選擇。這需要 Claude Code v2.1.280 或更新版本。

* 當您的管理員未設定[組織預設模型](#organization-default-model)時，[Default 選項](#default-model-setting)可以解析為已記錄的模型，此時選擇器的 Default 列會顯示該模型的名稱。
* 如果[模型限制](#restrict-model-selection)排除了已記錄的模型或該模型無法供您的帳戶使用，且您的管理員未設定組織預設模型，Default 選項會如同未記錄任何內容般進行解析。
* 如果您在 `/model` 中選擇 Default 或 `opusplan`，已記錄的選擇不會變更。

如果您使用 `/model` 切換模型，此切換也會影響[繼承主對話模型的 subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)，因為 Claude Code 會在 Claude 啟動它們時，根據您工作階段正在使用的模型來解析它們的模型。在 Claude 將研究或測試執行委派給其中一個 subagent 之前切換至 Opus，該工作也會在 Opus 上執行。若要讓自訂 subagent 維持使用較小的模型，請在其定義中設定 `model`。

如果您在使用 `-p` 旗標的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中以 `/model` 設定模型，您的選擇僅適用於目前的工作階段，不會儲存為預設值；在該模式下使用 `/model` 需要 Claude Code v2.1.205 或更新版本。專案和受管設定仍然優先，並會在下次啟動時重新套用。您的管理員設定為覆寫使用者選擇的[組織預設模型](#organization-default-model)也會在下次啟動時重新套用。

在 v2.1.144 至 v2.1.152 中，`/model` 僅適用於目前的工作階段，而選擇器中的 `d` 會儲存預設值。

`--model` 旗標和 `ANTHROPIC_MODEL` 環境變數僅適用於以它們啟動的工作階段。若要同時在不同終端機中執行不同的模型，請為每個終端機使用各自的 `--model` 旗標啟動，而非使用 `/model` 切換。

當 Claude Code 直接或透過代理其請求的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)與 Anthropic API 通訊時，`/model` 選擇器中會顯示價格，而某一列上的價格即為該列所選模型的價格。在 Amazon Bedrock 等[第三方供應商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)以及 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 上，由您的供應商或閘道決定您支付的費用，因此選擇器的各列不會顯示價格。價格僅為顯示標籤；它不會影響某一列所選擇的模型或您供應商的計費。在 v2.1.206 之前，[Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 和閘道工作階段會顯示 Anthropic 的牌價，且某一列可能顯示與其所選模型不同之模型的價格。

以 `claude --resume`、`--continue` 或 `/resume` 選擇器啟動的恢復工作階段，會保留逐字稿儲存時所使用的模型。如果還原的模型已停用或被 [`availableModels`](#restrict-model-selection) 排除，工作階段會改依一般的優先順序進行。在使用供應商專屬部署 ID 而非 Anthropic 模型 ID 的供應商上（例如 Amazon Bedrock、Google Cloud's Agent Platform 和 Microsoft Foundry），完全不會還原逐字稿中的模型，工作階段會透過一般的優先順序來解析其模型。

如果您的 `model` 設定為 `haiku`，在 Haiku 模型上儲存的工作階段會以 `haiku` 目前解析到的模型恢復。例如，一旦 `haiku` 解析為 Haiku 5.5，在 Haiku 4.5 上儲存的工作階段就會以 Haiku 5.5 恢復。

您透過 `--model` 或 `ANTHROPIC_MODEL` 為新啟動選擇的模型仍優先於還原的模型。自 v2.1.195 起，[`ANTHROPIC_DEFAULT_OPUS_MODEL`](#environment-variables) 系列變數也同樣優先。[`ANTHROPIC_DEFAULT_MODEL`](#set-a-default-model-for-new-sessions) 在其章節所列的條件下也可優先。

當啟動時的作用中模型來自專案或受管設定，而非您自己的選擇時，啟動標頭會顯示是哪個設定檔設定了它。執行 `/model` 即可覆寫；專案或受管設定會在下次啟動時重新套用。在嵌入 Claude Code 並設定 [`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`](https://code.claude.com/docs/zh-TW/env-vars) 的平台上，主機的模型設定優先於受管模型設定，而受管的 `availableModels` 允許清單仍然有效，除非主機提供自己的允許清單；[受管設定優先順序的例外情況](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)說明了主機會覆寫哪些鍵和變數。

如果您或您的組織設定了 [PreModelSwitch hook](https://code.claude.com/docs/zh-TW/hooks.md#premodelswitch)，它們會在所請求的切換套用之前執行，並可以阻擋切換或要求您確認。

當 Claude Code 無法判斷您組織的[受管外掛](https://code.claude.com/docs/zh-TW/settings-reference.md#enabledplugins)提供了哪些 PreModelSwitch hook 時（例如因為某個受管外掛載入失敗），它會拒絕切換，而不是在未經檢查的情況下套用，並在每次新的嘗試時再次檢查。關於訊息和復原方式，請參閱 [Model switch was blocked by a PreModelSwitch hook](https://code.claude.com/docs/zh-TW/errors.md#model-switch-was-blocked-by-a-premodelswitch-hook)。

當您透過 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 的 `setModel()` 方法、透過 [Desktop 應用程式](https://code.claude.com/docs/zh-TW/desktop.md)等應用程式，或從透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 連線的裝置切換模型時，Claude Code 會在切換時檢查該值：

* **Agent SDK 或應用程式**：在 Claude Code v2.1.268 或更新版本中，除非 Claude Code 在本機接受某個模型 ID（例如您的[自訂模型選項](#add-a-custom-model-option)），否則它會在工作階段首次切換至該 ID 時向您的供應商確認。此確認在所有供應商上都會執行，您的供應商未提供的 ID 會在切換時被拒絕，而不是在您下一次請求時才失敗。
* **Remote Control**：在 Anthropic API 上，Claude Code 會在本機檢查該值，不會傳送任何請求。

關於相關訊息，請參閱 [Model is not a recognized model id](https://code.claude.com/docs/zh-TW/errors.md#model-is-not-a-recognized-model-id) 和 [Model not found](https://code.claude.com/docs/zh-TW/errors.md#model-not-found)。

如果您以 `--model` 旗標、`ANTHROPIC_MODEL` 環境變數或 `model` 設定來設定模型，Claude Code 不會事先檢查，輸入錯誤的值會在第一次請求時產生 [There's an issue with the selected model](https://code.claude.com/docs/zh-TW/errors.md#theres-an-issue-with-the-selected-model)。

當所請求的模型有預定的停用日期，或會自動重新對應至較新版本時，Claude Code 會顯示一則指出所請求模型的警告。互動式工作階段會將其顯示為啟動通知。自 v2.1.182 起，在使用預設文字輸出格式時，相同的警告也會在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中寫入 stderr。此檢查也涵蓋在 [subagent frontmatter](https://code.claude.com/docs/zh-TW/sub-agents.md) 中設定的 `model`。對於 `--output-format json` 和 `stream-json`，stderr 警告會被隱藏；請改從[結果訊息](https://code.claude.com/docs/zh-TW/headless.md#get-structured-output)的 `modelUsage` 欄位讀取實際模型。

例如，在 Opus 上啟動工作階段：

```bash theme={null}
claude --model opus
```

然後在工作階段中切換模型：

```text theme={null}
/model sonnet
```

設定檔範例：

```json theme={null}
{
    "permissions": {
        "allow": ["Bash(npm run lint)"]
    },
    "model": "opus"
}
```

#### 為新工作階段設定預設模型

設定 `ANTHROPIC_DEFAULT_MODEL=<alias|name>` 以選擇您的工作階段預設啟動時使用的模型。需要 Claude Code v2.1.236 或更新版本。

只有在以下各項都未選擇模型時，Claude Code 才會以該變數的模型啟動新工作階段：

* `--model` 旗標
* `ANTHROPIC_MODEL`
* 任何設定檔中的 `model` 值，包括您以 `/model` 儲存的選擇
* [組織預設模型](#organization-default-model)

您以 `/model` 儲存的選擇在後續啟動時也優先於該變數。若改為設定 `ANTHROPIC_MODEL`，無論您以 `/model` 儲存了什麼，Claude Code 都會在下次啟動時回到該變數的模型。

除非適用組織預設模型，否則 Claude Code 也會將 Default 選項解析為該變數的模型。當 Default 選項解析為該變數的模型時，`/model` 選擇器中的 Default 列會顯示標籤 Set by ANTHROPIC\_DEFAULT\_MODEL。

在以下情況中，Claude Code 會忽略該變數，且 Default 選項會如同您未設定它般進行解析：

* 您將其設定為 `default`、`inherit`、`opusplan` 或 `haiku`
* [`enforceAvailableModels`](#enforce-the-allowlist-for-the-default-model) 已開啟
* 您組織的[模型限制](#restrict-model-selection)排除了該模型
* 該模型無法供您的帳戶使用

當新工作階段會以該變數的模型啟動時，您以 `claude --resume`、`--continue` 或 `/resume` 選擇器恢復的工作階段也會以該模型啟動。Claude Code 不會還原該工作階段逐字稿中儲存的模型。否則，當您[恢復工作階段](#setting-your-model)時，Claude Code 不會使用該變數。

#### 新工作階段以不同於您所選的模型啟動

當您以 `/model` 選擇模型，而下一個工作階段卻以其他模型啟動時，常見原因如下：

* **您只為單一工作階段選擇了它。** 在選擇器中按下 `s`、以 `--model` 啟動，以及在非互動模式中執行 `/model`，都只適用於目前的工作階段，不會變更您已儲存的預設值。
* **有更高優先順序的項目設定了模型。** 專案或受管設定中的 `model` 值、您 shell 中的 `ANTHROPIC_MODEL`，或您的管理員設定為覆寫使用者選擇的[組織預設值](#organization-default-model)，都會在每次啟動時重新套用。您的 `/model` 選擇仍然已儲存，只是被更高優先順序的設定所取代。當專案或受管設定設定了模型時，啟動標頭會指出該檔案。
* **Claude Code 無法儲存您的選擇。** `/model` 會將 `model` 寫入 `~/.claude/settings.json`。如果您無法寫入該檔案（例如因為另一個工具會產生它，或將它連結至唯讀副本），您選擇的模型只會在該工作階段中有效，下次啟動時會讀取舊值。請在產生該檔案的工具中設定 `model`，或讓該檔案可寫入。請參閱 [您在 Claude Code 中所做的變更在新工作階段中遺失](https://code.claude.com/docs/zh-TW/settings.md#a-change-you-made-in-claude-code-is-lost-in-new-sessions)。
* **您恢復了工作階段。** 您以 `claude --resume` 或 `--continue` 恢復的工作階段通常會[保留其原本使用的模型](#setting-your-model)，而非您目前的預設值。

## 限制模型選擇

管理員可以在[受管設定或政策設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中使用 `availableModels` 來限制使用者可以選擇的模型。項目可比對模型系列（例如 `sonnet`）、版本前綴（例如 `claude-sonnet-4-5`），或完整模型 ID（例如 `claude-sonnet-4-5-20250929`）。版本前綴也會比對以另一個區段延伸該前綴的後續模型 ID，因此 `claude-fable-5` 同時允許 Fable 5 與 Fable 5.1，而 `claude-fable-5-1` 僅允許 Fable 5.1。若要封鎖清單所允許的某個模型，或讓每個模型 ID 項目僅允許其所指定的版本，請參閱[封鎖特定模型或版本](#block-specific-models-or-versions)。

在內嵌 Claude Code 並設定 [`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`](https://code.claude.com/docs/zh-TW/env-vars) 的平台上，主機的模型設定優先於受管模型設定，而受管的 `availableModels` 允許清單仍然有效，除非主機提供自己的允許清單；[受管設定優先順序的例外](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)說明主機會覆寫哪些設定鍵與變數。

設定 `availableModels` 後，允許清單會套用於使用者可以指定模型的所有位置：

* **主要工作階段模型**：`/model`、`--model` 旗標、`ANTHROPIC_MODEL` 環境變數、`model` 設定、[`ANTHROPIC_DEFAULT_MODEL`](#set-a-default-model-for-new-sessions)，以及[恢復工作階段](#setting-your-model)時還原的模型
* **別名解析**：`ANTHROPIC_DEFAULT_OPUS_MODEL`、`ANTHROPIC_DEFAULT_SONNET_MODEL`、`ANTHROPIC_DEFAULT_HAIKU_MODEL` 與 `ANTHROPIC_DEFAULT_FABLE_MODEL` 環境變數無法將允許的別名重新導向至清單以外的模型
* **快速模式**：當切換會隱含地改用清單以外的 Opus 模型時，`/fast` 會拒絕切換，並顯示訊息「is not in your organization's allowed models」
* **Subagent 與隊員模型**：[subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model) frontmatter 中的 `model` 欄位、Agent 工具的 `model` 參數、[agent team](https://code.claude.com/docs/zh-TW/agent-teams.md#specify-teammates-and-models) 隊員模型、`CLAUDE_CODE_SUBAGENT_MODEL`，以及在 v2.1.197 及更早版本中 `/agents` 精靈內的模型選擇器&#x20;
* **Skill 與命令模型**：[skill 與命令](https://code.claude.com/docs/zh-TW/skills.md)中的 `model` frontmatter
* **顧問模型**：已設定的 [`advisorModel`](https://code.claude.com/docs/zh-TW/advisor) 設定與 `--advisor` 旗標
* **背景 agent 模型**：在 [Dispatch 選擇器](https://code.claude.com/docs/zh-TW/agent-view.md)中選取的模型

在 Anthropic API 與 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 上，模型系列別名（`opus`、`sonnet`、`haiku` 或 `fable`）在允許清單允許該模型時，會解析為其一般對應的模型。當允許清單封鎖該模型時，Claude Code 會改用允許清單所允許的該系列最新版本，並顯示一則通知，同時列出請求的模型與替代的模型。例如，使用 `["sonnet", "claude-opus-4-6"]` 時，`/model opus` 與 `--model opus` 都會選取 Claude Opus 4.6，也就是允許的最新 Opus。在 v2.1.205 之前，若別名的最新發行版本不在清單中，該別名會如同其他被封鎖的選擇一樣遭到拒絕或替換，即使清單允許較舊的版本也是如此。

替代需要有可改用的允許版本：當允許清單未允許該別名系列的任何版本時，該別名會如同其他被封鎖的值一樣，遵循下列拒絕與替換行為。

Claude Code 會依據模型的設定位置來處理其他被封鎖的選擇：

* **`/model`**：Claude Code 會以錯誤拒絕切換
* **`--model` 旗標、`ANTHROPIC_MODEL` 或 `model` 設定**：Claude Code 會在啟動時替換該值，並顯示同時列出請求模型與替代模型的警告，工作階段會以預設模型啟動
* **[`ANTHROPIC_DEFAULT_MODEL`](#set-a-default-model-for-new-sessions)**：Claude Code 會忽略該變數
* **Subagent 或隊員覆寫**：Claude Code 會以備援模型執行該 subagent 或隊員，而不是讓請求失敗。subagent 的備援請參閱[選擇模型](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)，隊員的備援請參閱[指定隊員與模型](https://code.claude.com/docs/zh-TW/agent-teams.md#specify-teammates-and-models)。

  在互動式工作階段中，當 Claude Code 透過此備援或上述的最新允許版本替代來替換 subagent 的模型時，會向您發出警告，並列出請求的模型與替代的模型；隊員的備援則不會回報。

  在上述最新允許版本替代適用的情況下，被封鎖的系列別名會改為遵循該替代方式。在 v2.1.222 之前，別名在所有提供者上都會如同其他被封鎖的值一樣改用備援
* **Skill 或命令覆寫**：Claude Code 會忽略該覆寫（包括被封鎖的系列別名），skill 或命令會以工作階段模型執行。[在 subagent 中執行](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent)的 skill 或命令則改為遵循上述的 subagent 行為
* **`advisorModel` 設定**：該工作階段會停用顧問
* **`--advisor` 旗標**：Claude Code 會在啟動時以錯誤結束。在[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)中，則會在沒有顧問的情況下啟動工作階段，而不是結束
* **`CLAUDE_CODE_AUTO_MODE_MODEL`**：Claude Code 會忽略該變數，並如同您未設定它一般，為其[自動模式分類器請求](https://code.claude.com/docs/zh-TW/permission-modes.md#default-classifier-model)選擇模型

Claude Code 會在 `/model` 選擇器中隱藏被排除的模型。您列出的模型 ID 是否也會擁有獨立的一列，則依提供者而有所不同：

* **Anthropic API、[Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、[Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway)，或透過 `ANTHROPIC_BASE_URL` 設定的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)**：您列出但沒有內建選擇器列的 Anthropic 模型 ID，會顯示為獨立的標示列。Claude Code 會為 Opus、Sonnet 與 Haiku 版本新增這類列，例如清單所固定的較舊版本。如果您在 [`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#modelpicker) 陣容中設定 `replaceBuiltInOptions`，該列就不會出現。在 v2.1.199 之前，這類 ID 只能透過輸入 `/model <id>` 來選取。
* **Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry**：除非您列出的模型 ID 以 `anthropic.` 開頭，否則 Claude Code 不會為其新增列，無論它是 Anthropic 模型 ID 或提供者專屬的 ID。[Mantle 模型 ID](#mantle-model-ids) 帶有該前綴。若要顯示沒有內建列的列出版本，請同時將其加入 [`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#modelpicker) 陣容，該陣容接受您提供者格式的 ID。

Claude Code 代您進行的模型變更也會以相同方式檢查：

* **[備援模型鏈](#fallback-model-chains)**：允許清單以外的項目會被捨棄
* **Plan mode 升級**：在 Anthropic API 與 Claude Platform on AWS 上，升級至被排除的模型（例如 [`opusplan`](#opusplan-model-setting)）時，會使用升級系列中允許的最新版本。在使用提供者專屬模型 ID 的提供者上，以及沒有任何允許版本時，會略過升級，規劃會以工作階段的模型繼續進行
* **[自動模型備援](#automatic-model-fallback)**：目標被排除的備援不會執行，因此被標記的請求會改以拒絕結束
* **[自動模式分類器](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)**：當允許清單排除[預設分類器模型](https://code.claude.com/docs/zh-TW/permission-modes.md#default-classifier-model)時，原本會使用該模型的分類器請求會改以工作階段的模型執行，或在 [Fable](#work-with-fable) 工作階段中改以 Opus 模型執行。在 Anthropic API 以外的提供者上，該 Opus 備援會以您在 `ANTHROPIC_DEFAULT_OPUS_MODEL` 中設定的模型執行，否則使用 Opus 5，且不會參照允許清單。需要 Claude Code v2.1.210 或更新版本
* **[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)**：若啟用快速模式後工作階段所使用的模型不在允許清單中，將會拒絕啟用快速模式
* **Amazon Bedrock 與 Google Cloud 的 Agent Platform 上的可用性備援**：當您的帳戶在工作階段中途失去某個模型的存取權時，切換至其他模型時會略過被排除的模型。[Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#when-your-organization-enforces-a-model-allowlist) 與 [Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#when-your-organization-enforces-a-model-allowlist) 上的啟動模型檢查，僅在受管設定也設定了 [`enforceAvailableModels`](#enforce-the-allowlist-for-the-default-model) 時才會略過被排除的模型

```json theme={null}
{
  "availableModels": ["sonnet", "haiku"]
}
```

### 使用介面涵蓋範圍

每個使用介面都會強制執行其收到的允許清單。各使用介面接收設定的傳遞機制則有所不同：

| 傳遞機制 | CLI 與 IDE | Desktop 本機工作階段 | 網頁、行動裝置與雲端工作階段 | Agent SDK 與非互動模式 | Cowork |
| :- | :- | :- | :- | :- | :- |
| 來自管理主控台的[伺服器管理設定](https://code.claude.com/docs/zh-TW/server-managed-settings.md) | 強制執行 | 強制執行 | 強制執行，[Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段除外 | 強制執行 | 遠端 Cowork 工作階段：由伺服器檢查模型。在使用者的電腦上：不會傳遞。 |
| [MDM 或受管設定檔](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms) | 強制執行 | 強制執行 | 在 Anthropic 託管的環境中不會傳遞；在[自行託管的環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中，依照 [Claude Code 如何合併受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)從 runner 映像檔強制執行 | 強制執行 | 在已部署處強制執行 |

* [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)（包括您從 Desktop 應用程式啟動的工作階段）預設在 Anthropic 管理的 VM 上執行：部署到您裝置上的設定不會傳遞至這些工作階段，因此請透過伺服器管理設定傳遞允許清單。您的組織路由至[自行託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)的工作階段會在您自己的運算資源上執行，並且也會讀取 runner 映像檔中的受管設定檔。[Claude Code 如何合併受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)說明該檔案何時適用。在雲端工作階段中，若請求的模型被允許清單排除，工作階段中途的模型切換將被拒絕。當您伺服器管理設定中的 `availableModels` 清單不為空時，伺服器會拒絕在 claude.ai/code 或從 Desktop 應用程式以清單所排除的模型啟動雲端工作階段的請求。
* [Claude Tag](https://claude.com/docs/claude-tag/overview) 工作階段在雲端環境中執行，但不會收到伺服器管理設定；在[自行託管環境](https://code.claude.com/docs/zh-TW/self-hosted-environments)中，這些工作階段仍會讀取 runner 映像檔中的受管設定檔。若要為這些工作階段設定模型，請參閱 Claude Tag 管理員指南中的[為範圍選擇模型](https://claude.com/docs/claude-tag/admins/customize#choose-the-model-for-a-scope)。
* Cowork 是 Claude Desktop 應用程式中的 agentic 工作分頁，其工作階段在 Claude Code 上執行，但依設計不會收到來自 claude.ai 管理主控台的伺服器管理設定。當您伺服器管理設定中的 `availableModels` 清單不為空，且使用者選擇了清單以外的模型時，伺服器會在遠端 Cowork 工作階段中拒絕該模型。當受管設定檔存在於工作階段執行的位置時，該檔案即適用於 Cowork 工作階段；遠端 Cowork 工作階段在 Anthropic 管理的 VM 上執行，部署到裝置上的檔案不會存在於該處。
* 在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 與 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 等[第三方提供者](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)上的工作階段不會收到伺服器管理設定，因此在這些環境中請透過 MDM 或受管設定檔傳遞允許清單。
* 從管理主控台傳遞還需要工作階段以登入您組織的[符合資格的登入](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)，或為該組織核發的 OAuth token 來擷取設定。對於以 API 金鑰驗證的裝置群組，無論金鑰是直接設定或由 [`apiKeyHelper`](https://code.claude.com/docs/zh-TW/settings-reference#apikeyhelper) 指令碼產生，請透過 MDM 或受管設定檔傳遞允許清單。
* Desktop 的 Code 分頁也承載 [SSH 工作階段](https://code.claude.com/docs/zh-TW/desktop.md#ssh-sessions)，這些工作階段會從其執行所在的遠端主機讀取受管設定檔。請參閱 [Desktop 受管設定](https://code.claude.com/docs/zh-TW/desktop.md#managed-settings)。
* claude.ai 與 Desktop 應用程式中的模型選擇器會隱藏或以灰色顯示被組織允許清單排除的模型。選擇器狀態僅是為使用者提供的便利，並不會強制執行允許清單。

### 預設模型行為

在預設的前綴比對下，單獨使用 `availableModels` 時，Default 選項會維持為帳戶的系統[執行階段預設](#default-model-setting)，直到您同時設定 [`enforceAvailableModels`](#enforce-the-allowlist-for-the-default-model)。如果該預設是您想要限制的模型，請一併設定 `enforceAvailableModels`，或[封鎖該模型](#block-specific-models-or-versions)。

使用 `availableModels: []` 時，指名的模型選擇都會被封鎖，且 `enforceAvailableModels` 不會產生作用。

### 為 Default 模型強制執行允許清單

在受管設定中，將 `enforceAvailableModels: true` 與非空的 `availableModels` 一起設定，即可將允許清單延伸至 Default 選項。這需要 Claude Code v2.1.175 或更新版本。

```json theme={null}
{
  "availableModels": ["sonnet", "haiku"],
  "enforceAvailableModels": true
}
```

對於[帳戶上未記錄模型](#setting-your-model)的成員，Default 選項會解析為帳戶類型預設，或在管理員已設定時解析為[組織預設模型](#organization-default-model)。當該模型不在允許清單中時，Default 選項會改為解析為第一個指定了允許且可用模型的 `availableModels` 項目，而 `/model` 選擇器的 Default 列會顯示該模型。這適用於所有使用預設的地方：工作階段啟動、在 `/model` 中選取 Default、[備援模型鏈](#fallback-model-chains)中的 `"default"` 關鍵字，以及捨棄被排除的選擇時所使用的備援。記錄在成員帳戶上的模型也會依 `availableModels` 進行檢查；[設定您的模型](#setting-your-model)說明 Default 選項如何處理它。

`enforceAvailableModels` 僅在 `availableModels` 不為空時才會重新對應 Default 選項。當 `availableModels` 不為空，但沒有任何項目解析為允許且可用的模型時，會略過強制執行，並顯示僅在 `--debug` 下可見的警告。請在清單中至少保留一個保證可用的項目以避免這種情況。

請將這兩個設定鍵一起部署在您所傳遞的最高等級受管來源中。預設情況下，Claude Code 只會讀取該來源，因此當管理主控台傳遞任何設定時，放在受管設定檔中的這組設定會被忽略；在 [Claude Code 如何合併受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)中所述的選擇性合併下，Claude Code 仍會忽略來自等級低於設定 `availableModels` 之來源的 `modelOverrides` 對應。

### 控制使用者執行的模型

`model` 設定是初始選擇，而非強制執行。它會設定工作階段啟動時使用的模型，但使用者仍可開啟 `/model` 並選擇 Default，而 Default 會解析為系統的[執行階段預設](#default-model-setting)，不論 `model` 設定為何，除非 [`enforceAvailableModels`](#enforce-the-allowlist-for-the-default-model) 或[封鎖特定版本的設定鍵](#block-specific-models-or-versions)對其適用。

若要完整控制模型體驗，請結合下列設定：

* **`availableModels`**：限制使用者可以切換的指名模型
* **`enforceAvailableModels`**：將 `availableModels` 允許清單延伸至 Default 選項，使 Default 無法解析為清單以外的模型
* **`deniedModels`** 與 **`availableModelsMatch`**：[封鎖特定版本](#block-specific-models-or-versions)，這些版本原本會被某個 `availableModels` 項目所允許
* **`model`**：設定工作階段啟動時的初始模型選擇
* **`ANTHROPIC_DEFAULT_SONNET_MODEL`** / **`ANTHROPIC_DEFAULT_OPUS_MODEL`** / **`ANTHROPIC_DEFAULT_HAIKU_MODEL`** / **`ANTHROPIC_DEFAULT_FABLE_MODEL`**：控制 `sonnet`、`opus`、`haiku` 與 `fable` 別名所解析的目標，以及[帳戶類型預設](#default-model-setting)所使用的版本

此範例讓使用者以 Sonnet 4.5 開始，將選擇器限制為 Sonnet 與 Haiku，並確保 Default 解析為允許清單上的模型，而非層級預設：

```json theme={null}
{
  "model": "claude-sonnet-4-5",
  "availableModels": ["claude-sonnet-4-5", "haiku"],
  "enforceAvailableModels": true,
  "env": {
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-5"
  }
}
```

若沒有 `enforceAvailableModels` 或 `env` 區塊，在選擇器中選取 Default 的使用者會取得[執行階段預設](#default-model-setting)，而不是 `model` 中固定的版本。這兩項設定涵蓋不同的範圍：`enforceAvailableModels` 讓 Default 遵循允許清單，而 `env` 區塊則固定允許的別名（例如 `sonnet`）所解析的版本。若僅限制模型系列就已足夠，請單獨使用 `enforceAvailableModels`；若您還需要固定特定版本，請加上 `env` 區塊。

### 合併行為

當 Claude Code 套用的受管設定定義了 `availableModels` 時，只會套用該清單，[自行提供清單的主機平台](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)除外：使用者、專案或本機設定中的項目無法擴充它，且 Claude Code 也絕不會跨受管來源合併 `availableModels`；[Claude Code 如何合併受管來源](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)說明套用哪個來源的清單。否則，來自使用者、專案與本機設定的清單會如同其他陣列設定一樣[串接並去除重複](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)。在 Claude Code v2.1.175 之前，來自較低優先順序範圍的項目會合併至受管清單，而不是被其取代。

在有效清單中，指定某系列中特定模型的項目（無論是版本前綴或完整模型 ID）會停用該系列的萬用字元項目。例如，使用 `["sonnet", "claude-sonnet-4-5"]` 時，使用者只能選取 `claude-sonnet-4-5` 所[比對](#restrict-model-selection)的模型 ID，而不是所有 Sonnet 模型。

### Mantle 模型 ID

`availableModels` 中以 `anthropic.` 開頭的項目會以自訂選項的形式加入 `/model` 選擇器。這是[為第三方部署固定模型](#pin-models-for-third-party-deployments)中所述別名比對的例外。啟用 [Amazon Bedrock Mantle 端點](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint)時，Claude Code 會將符合 Mantle 格式的項目路由至該端點。該設定仍會將選擇器限制為列出的項目，而且 Mantle ID 內嵌了系列名稱，因此會被視為特定項目並停用該系列的萬用字元：除了任何 Mantle ID 之外，請列出您希望保持可選取的版本前綴或完整 ID。請參閱[合併行為](#merge-behavior)。

### 封鎖特定模型或版本

`claude-opus-5` 這類 `availableModels` 項目，一旦 Claude Code 支援延伸它的後續版本（例如 Opus 5.5），也會允許這些版本。有兩個受管設定可讓您暫緩某個版本，且兩者都需要 Claude Code v2.1.283 或更新版本：

* [`deniedModels`](https://code.claude.com/docs/zh-TW/settings-reference#deniedmodels)：列出要封鎖的模型。列出的模型即使 `availableModels` 允許也會被封鎖，且此設定鍵在完全沒有允許清單時也能運作。沒有任何項目封鎖的版本會維持允許
* [`availableModelsMatch`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodelsmatch)：將其設定為 `"exact"`，使 `availableModels` 中的每個模型 ID 僅允許其所指定的版本。如此一來，列出的模型 ID 的較新版本會維持封鎖，直到您將其加入清單

較早的版本會忽略這兩個設定鍵，因此請一併設定 [`requiredMinimumVersion`](https://code.claude.com/docs/zh-TW/settings-reference#requiredminimumversion) 以防止這些版本啟動。

此範例允許 Opus 與 Sonnet 模型，並封鎖所有寫法的 Opus 5.5，包括帶日期與提供者專屬的 ID：

```json theme={null}
{
  "availableModels": ["opus", "sonnet"],
  "deniedModels": ["claude-opus-5-5"]
}
```

被封鎖的模型（無論是 `deniedModels` 指名的，或是 `"exact"` 清單所省略的）在[允許清單適用](#restrict-model-selection)的所有位置都會被視為被封鎖的選擇。它會從 `/model` 選擇器中隱藏，且 `/model <name>` 會拒絕它。如果您透過 `--model`、`ANTHROPIC_MODEL` 或 `model` 設定指定被封鎖的模型 ID，Claude Code 會在啟動時捨棄它，改為解析 Default 選項。如果 [hook](https://code.claude.com/docs/zh-TW/hooks.md) 或背景請求指定了 `deniedModels` 封鎖的模型（例如 agent hook 的 `model` 欄位），該請求會改以工作階段的模型執行。

Default 選項同樣遵循這兩個設定鍵，無論您是否設定 [`enforceAvailableModels`](#enforce-the-allowlist-for-the-default-model)。如果您將其與非空的 `availableModels` 一起設定，被封鎖的預設會被視為允許清單以外的模型。否則，會解析為被封鎖模型的 Default 選項將依下列順序降級：

1. 同一系列中允許的最新版本
2. 依序為每個較低成本系列中允許的最新模型：先 Sonnet，再 Haiku
3. 第一個指定了允許模型的 `availableModels` 項目

如果上述皆不被允許，以 Default 選項啟動的工作階段會[拒絕啟動](https://code.claude.com/docs/zh-TW/errors.md#managed-settings-block-the-default-model)，並顯示指出需修正之設定鍵的錯誤。`"exact"` 清單僅在受管的 `availableModels` 清單至少指定一個模型或系列時，才會影響 Default 選項。

Claude Code 僅從受管設定讀取這兩個設定鍵。如果您在使用者、專案或本機設定中，或透過 `--settings` 設定其中任一項，Claude Code 會忽略它並顯示警告。

### 組織模型限制

Claude Enterprise 方案的組織管理員可以在 claude.ai 管理主控台中停用個別模型，藉此限制成員可以執行的模型。此限制會在 Claude Code 驗證時隨帳戶的權利一併傳遞，與設定中的任何 `availableModels` 清單分開，且伺服器在建立工作階段時也會獨立強制執行相同的限制。需要 Claude Code v2.1.187 或更新版本。

此限制適用於成員登入或使用自己的 API 金鑰時。組織範圍的憑證（例如組織服務金鑰）不與使用者綁定，因此限制不適用於這些憑證。

Claude Console 沒有模型限制控制項。沒有 Claude Enterprise 方案的組織（包括其成員透過 Anthropic API 驗證的組織），請改用[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中的 [`availableModels`](#restrict-model-selection) 來限制模型，並加上 [`enforceAvailableModels`](#enforce-the-allowlist-for-the-default-model) 以涵蓋 Default 選項。[使用介面涵蓋範圍](#surface-coverage)說明每個使用介面如何接收並強制執行這些設定。

受限制的模型會從 `/model` 選擇器中隱藏。透過 `--model`、`ANTHROPIC_MODEL` 環境變數或 `model` 設定以名稱選取它時，會顯示通知 `Model "<name>" is restricted by your organization's settings. Using <model> instead.`，且工作階段會以允許的模型啟動。針對受限制的模型輸入 `/model <name>` 會被拒絕，並顯示 `Model '<name>' is restricted by your organization's settings. Run /model to choose a different model.`，工作階段會保留其目前的模型。

`opus` 這類[模型系列別名](#restrict-model-selection)在組織允許時會解析為其一般對應的模型。當組織限制該模型時，Claude Code 會改用組織所允許的該系列最新版本，並顯示相同的替代通知。只有在其系列的所有版本都受限制時，`/model <alias>` 才會被拒絕；在這種情況下，透過 `--model`、`ANTHROPIC_MODEL` 或 `model` 設定的別名仍會在啟動時被替換。在 v2.1.205 之前，系列別名僅依其最新發行版本來決定替代或拒絕，即使允許較舊的版本也是如此。

限制可套用於整個組織或依角色套用：

* 在組織層級停用某個模型，會對所有成員移除該模型。
* 角色層級存取權會將不同模型授予不同的自訂角色，而擁有多個角色的成員可以使用其任一角色所授予的任何模型。
* Haiku 模型永遠可用且無法停用，因此每位成員至少保有一個可用的模型。
* 存取權變更會在約一分鐘內對新請求生效；`/model` 選擇器則會在下一次工作階段啟動時反映變更。

兩種限制會同時套用：只有在模型被 `availableModels` 允許且未被組織限制時，才可選取該模型。組織限制僅適用於 Anthropic API 與 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)部署上的工作階段；在其他任何提供者上，請改用 `availableModels`。

## 組織預設模型

Claude Enterprise 方案的組織管理員可以從 claude.ai 管理主控台為 Claude Code 成員設定預設模型，適用於整個組織或個別自訂角色。設定後，Default 選項會解析為該模型。需要 Claude Code v2.1.196 或更新版本。

`/model` 選擇器中的 Default 列會顯示組織預設模型的名稱，並標示 Org default。無論管理員是為整個組織還是為您的角色設定預設值，標籤都會顯示 Org default。角色預設值涵蓋該自訂角色的成員，並優先於全組織的預設值；當您的多個角色設定了不同的預設值時，會套用能力最強的模型。

組織預設值是一個起點，而非限制。以下選擇優先於組織預設值：

* `--model` 旗標與 `ANTHROPIC_MODEL` 環境變數
* [受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中的 `model` 值，或透過 `--settings` 提供的 `model` 值
* 您的使用者、專案或本機設定中的 `model` 值，包括您透過 `/model` 儲存的模型

管理員也可以將組織預設值設定為覆寫使用者的選擇。啟用覆寫後，組織預設值會優先於使用者、專案與本機設定中的 `model` 值，因此您透過 `/model` 儲存的模型只會套用於目前的工作階段，下次啟動時會恢復為組織預設值。當您的選擇不同時，`/model` 會顯示 `Your organization's default (<model>) applies on restart`。即使啟用覆寫，`--model` 旗標、`ANTHROPIC_MODEL`、受管設定與 `--settings` 仍然優先。

若要限制成員可選擇的模型，請改用[組織模型限制](#organization-model-restrictions)或 [`availableModels`](#restrict-model-selection)。

Claude Code 只會在啟動時讀取一次組織預設值，因此管理員在工作階段期間變更的預設值會在下次啟動時生效。

當組織預設值未覆寫使用者選擇時，管理員變更預設值後的第一次互動式啟動會從您的使用者設定中清除一次 `model` 鍵，讓新的預設值生效。此操作不會變更檔案中的其他任何內容，而您在該次啟動之後透過 `/model` 儲存的模型會被保留。

組織預設值在被採用之前，會經過以下限制檢查：

* 在預設的前綴比對下，單獨使用 [`availableModels`](#restrict-model-selection) 不會套用於組織預設值，因此不在允許清單中的組織預設值仍會套用。若同時設定了 [`enforceAvailableModels`](#enforce-the-allowlist-for-the-default-model)，不在允許清單中的組織預設值也會被重新對應至允許清單中的第一個項目
* 若[組織模型限制](#organization-model-restrictions)拒絕您的帳戶使用組織預設模型，該模型會被替換為同一系列中最新的允許模型；若該系列的所有版本都受到限制，則替換為成本較低的系列
* 關於被 `deniedModels` 或 `"exact"` 清單封鎖的組織預設值，請參閱[封鎖特定模型或版本](#block-specific-models-or-versions)
* 若組織預設模型完全無法供您的帳戶使用，則會被略過，而 Default 選項會如同[沒有組織預設值](#default-model-setting)時一樣進行解析

自 v2.1.199 起，當組織預設值與您帳戶類型的一般預設值屬於不同的模型系列時，`/model` 選擇器會為該一般系列保留獨立的一列，讓您仍可在工作階段中切換至該系列。在 v2.1.196 至 v2.1.198 中，選擇器中沒有該列。

組織預設值僅適用於透過 Anthropic API 驗證的工作階段。若要在其他任何地方設定預設值，包括 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)部署，請改用[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中的 `model` 鍵。

## 組織 effort 限制

您的組織可以透過兩種方式限制 [effort 等級](#adjust-effort-level)。在 Claude Enterprise 方案中，組織管理員可設定各角色的 effort 限制，詳見下文。在任何方案與任何供應商上，包括 Amazon Bedrock、Google Cloud 的 Agent Platform 以及 Microsoft Foundry，[`maxEffortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#maxeffortlevel) 受管設定則改為在用戶端限制 effort。當兩者同時適用於某個模型時，將套用較低的上限。

Claude Enterprise 方案的組織管理員可以為每個自訂角色，針對各模型設定最高 [effort 等級](#adjust-effort-level)，並搭配角色層級的[組織模型限制](#organization-model-restrictions)。需要 Claude Code v2.1.195 或更新版本。

* 高於上限的等級不會出現在 `/effort` 選擇器中，而透過 `--effort` 或 `/effort` 指定更高等級時，則會改以上限等級執行。若您以高於上限的 `--effort` 啟動純文字 `--print` 執行，stderr 上會顯示一則警告，列出所要求的等級與實際套用的等級。在互動式工作階段中、使用 `json` 或 `stream-json` 輸出時，或在背景 agent 中，該警告則會改為寫入[除錯日誌](https://code.claude.com/docs/zh-TW/errors.md#configuration-warnings)。
* 上限是以模型為單位，因此切換模型可能會改變可用的等級。
* 當您的多個角色授予同一個模型時，將套用限制最寬鬆的上限。

Effort 限制會與[組織模型限制](#organization-model-restrictions)一同傳送，並套用至相同的工作階段。

## 特殊模型行為

### `default` 模型設定

`default` 的行為取決於您的帳戶類型：

* **Pro、Max、Ultra、Team、Enterprise 和 Anthropic API**：預設為 Opus 5.5
* **Claude Platform on AWS、Amazon Bedrock 和 Google Cloud's Agent Platform**：預設為 Opus 5.5
* **Microsoft Foundry**：預設為 Sonnet 4.5

在 v2.1.280 之前，`default` 在 Pro 和 Team Standard 上解析為 Sonnet 5；自 v2.1.219 起，在 Max、Ultra、Team Premium、Enterprise、Anthropic API、Claude Platform on AWS、Amazon Bedrock 和 Google Cloud's Agent Platform 上解析為 Opus 5。在 v2.1.219 之前，自 v2.1.154 起，`default` 在 Anthropic API、Max、Ultra、Team Premium 和 Enterprise 隨用隨付方案上解析為 Opus 4.8；自 v2.1.207 起，在 Claude Platform on AWS、Amazon Bedrock 和 Google Cloud's Agent Platform 上也解析為 Opus 4.8。在 v2.1.207 之前，`default` 在 Claude Platform on AWS 上解析為 Opus 4.7，在 Amazon Bedrock 和 Google Cloud's Agent Platform 上解析為 Sonnet 4.5。

當管理員設定了[組織預設模型](#organization-default-model)時，`default` 會解析為該模型，而非上述的帳戶類型預設值。需要 Claude Code v2.1.196 或更新版本。在其章節所列的條件下，`default` 也可能解析為您透過 [`ANTHROPIC_DEFAULT_MODEL`](#set-a-default-model-for-new-sessions) 設定的模型，或解析為[記錄在您帳戶上](#setting-your-model)的模型。

當您的帳戶上沒有記錄任何模型、受管設定[對 Default 模型強制執行允許清單](#enforce-the-allowlist-for-the-default-model)，且帳戶類型預設值不在 `availableModels` 中時，`default` 會解析為強制執行的 Default，而非上述的帳戶類型預設值。當組織預設值與強制執行同時適用時，組織預設值會先取代帳戶類型預設值，接著再對其套用強制執行：位於允許清單內的組織預設值會保留，而不在清單內的則會解析為強制執行的 Default。

在任何方案或供應商上，Fable 模型都不是帳戶類型預設值。使用 `/model` 選擇其中一個模型時，會將其儲存為您使用者設定中的所選模型，因此之後的工作階段都會以該模型啟動。關於 Claude Code 在 v2.1.257 中對已儲存的 Fable 5 選擇所做的一次性變更，請參閱[使用 Fable](#work-with-fable)。

### `opusplan` 模型設定

`opusplan` 模型別名提供一種自動化的混合方式：

* **在 plan mode 中**：使用 `opus` 進行複雜推理和架構決策
* **在執行模式中**：自動切換至 `sonnet` 進行程式碼產生與實作

這種方式將 Opus 在規劃上的推理能力與 Sonnet 在執行上的效率結合在一起。

plan mode 的 Opus 階段使用與 `opus` 模型設定相同的上下文視窗，而執行階段則使用與 `sonnet` 相同的視窗。當 `opus` 和 `sonnet` 解析為預設以 [1M 上下文視窗](#extended-context)執行的模型時（如目前 Anthropic API 上的模型），兩個階段都會以 1M 視窗執行。若要在不是這種情況時為兩個階段請求 1M 上下文，請將[模型設定](#setting-your-model)為 `opusplan[1m]`，例如使用 `/model opusplan[1m]`。使用 `/model` 設定需要 Claude Code v2.1.265 或更新版本；在較早的版本上，請改用 `--model` 旗標或 `model` 設定。

當 [`availableModels`](#restrict-model-selection) 排除了最新的 Opus 但允許較舊版本時（例如 `["sonnet", "claude-opus-4-6"]`），`opusplan` 會使用允許的最新 Opus 進行規劃，只有在所有 Opus 都被排除時才會維持使用 Sonnet。同樣地，通常會在 plan mode 中升級為 Sonnet 的 Haiku 工作階段，會使用允許的最新 Sonnet，只有在所有 Sonnet 都被排除時才會維持使用 Haiku。在 v2.1.205 之前，只要升級家族的最新版本被排除，即使允許清單允許較舊版本，plan mode 也會維持使用工作階段的模型。

以較舊的允許版本替代的行為適用於 Anthropic API 和 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)。在 Amazon Bedrock、Google Cloud's Agent Platform、Microsoft Foundry 和 Mantle 上，由於其部署使用供應商專屬的模型 ID，只要升級模型被排除，plan mode 就會維持使用工作階段的模型。

若想採用由 Claude 在任務進行中自行決定何時諮詢第二個模型、而非在規劃邊界切換的混合方式，請參閱 [advisor 工具](https://code.claude.com/docs/zh-TW/advisor.md)。

### 備援模型鏈

當主要模型過載、無法使用，或傳回其他不可重試的伺服器錯誤時，Claude Code 可以切換至備援模型，而不是讓請求失敗。身分驗證、計費、速率限制、請求大小和傳輸錯誤，以及[被您組織的政策檢查拒絕](https://code.claude.com/docs/zh-TW/errors.md#automatic-retries)，都不會觸發切換；這些情況會依照其一般的重試和錯誤處理方式進行。當 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#when-a-model-is-disabled-mid-session) 或 [Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md#when-a-model-is-disabled-mid-session) 拒絕您帳戶無法呼叫的模型時，Claude Code 確實會切換，因為它將此視為模型無法使用，而非身分驗證錯誤。

設定一個或多個備援模型後，Claude Code 會依序嘗試這些模型，並在切換時顯示通知。切換僅在目前回合內有效，因此您的下一則訊息會再次優先嘗試主要模型。Claude Code 在移除重複項目後，將模型鏈上限設為三個模型，並忽略多餘的項目。

使用 `--fallback-model` 旗標為單一工作階段設定模型鏈，此旗標接受以逗號分隔的清單：

```bash theme={null}
claude --fallback-model sonnet,haiku
```

若要在工作階段之間保留模型鏈，請在[設定](https://code.claude.com/docs/zh-TW/settings.md)中將 `fallbackModel` 設定為陣列：

```json theme={null}
{
  "fallbackModel": ["claude-sonnet-5", "claude-haiku-4-5"]
}
```

`--fallback-model` 旗標優先於 `fallbackModel` 設定。每個項目都接受模型名稱或別名，而 `"default"` 會展開為預設模型。

Claude Code 在啟動時不會確認模型鏈，`/status` 也不會顯示它。發生切換時顯示的通知，是已設定備援的第一個可見跡象。

當請求進行容錯移轉時，Claude Code 會依序嘗試每個項目，直到其中一個接受請求為止。同樣無法連線的項目（例如在設定中釘選的已淘汰模型）也會以相同方式移轉至下一個項目。Claude Code 會在開始依序嘗試之前移除兩類項目：

* **不在允許清單內**：Claude Code 在讀取模型鏈時，會捨棄任何未被 [`availableModels`](#restrict-model-selection) 允許的項目。
* **壓縮期間上下文視窗較小**：模型鏈也涵蓋[壓縮](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)，但 Claude Code 不會改用上下文視窗比主要模型小的模型，因為在那裡進行摘要會先截斷部分對話。如果所有備援模型的視窗都較小，壓縮會顯示原始錯誤，您可以重試。

Claude Code 也會將模型鏈套用至 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)。當 subagent 的請求進行容錯移轉時，Claude Code 會依序嘗試您設定的備援模型，subagent 則會在接受請求的模型上繼續執行。您工作階段的模型不會改變。在 v2.1.247 之前，模型鏈涵蓋的失敗會直接結束 subagent。

### 自動模型備援

本節說明從 Fable 模型、Opus 5.5、Sonnet 5.5 和 Opus 5 進行的基於內容的備援。關於模型過載或無法使用時基於可用性的備援，請參閱[備援模型鏈](#fallback-model-chains)。

Fable 模型、Opus 5.5、Sonnet 5.5 和 Opus 5 會搭配安全分類器執行，這些分類器最常標記網路安全和生物學內容。對於這兩個類別，備援模型取決於拒絕的模型：

* **Fable 5.1、Fable 5 和 Opus 5.5**：被標記為生物學的請求會在 Opus 5 上重新執行，被標記為網路安全的請求會在 Opus 4.8 上重新執行。
* **Sonnet 5.5**：被標記為網路安全的請求會在 Sonnet 5 上重新執行。被標記為生物學的請求則會以拒絕結束，因為 Sonnet 5.5 沒有生物學備援模型。
* **Opus 5**：被標記為網路安全的請求會在 Opus 4.8 上重新執行。被標記為生物學的請求則會以拒絕結束，因為 Opus 5 執行自己的生物學分類器，且沒有備援模型。

在 Amazon Bedrock、Google Cloud's Agent Platform 和 Microsoft Foundry 上，Claude Code 改為透過您部署的模型 ID 解析這些目標。請參閱[在 Bedrock、Agent Platform 和 Foundry 上啟用備援](#enable-fallback-on-bedrock-agent-platform-and-foundry)。

當 Claude Code 將被標記的請求切換至其類別的備援模型時，會在該模型上重新執行請求。在您的主要對話中，它會在逐字稿中顯示通知。若要在切換前先被詢問，請參閱[切換前先詢問](#ask-before-switching)。

發生備援後，工作階段會在備援模型上繼續。若要返回原始模型，請執行 [`/model`](#setting-your-model)。

基於類別的備援需要 Claude Code v2.1.219 或更新版本。在 v2.1.219 之前，每個被標記的 Fable 5 請求都會在您供應商的預設 Opus 模型上重新執行，而 Opus 5 不是備援來源。

備援模型會對照 [`availableModels`](#restrict-model-selection) 進行檢查。當它被封鎖時，不會發生備援。拒絕會以一般錯誤顯示，且工作階段的模型不會改變。

#### 備援後的 effort 等級

當 Claude Code 將您的工作階段切換至備援模型時，會保留被標記請求執行時的 effort 等級。例如，在 Opus 5.5 上以其預設 `medium` 執行、備援至 Opus 4.8 的工作階段會維持在 `medium`，儘管 Opus 4.8 預設為 `high`。

在下列情況中，會套用不同的等級：

* **您自己的變更**：一旦您選擇 effort 等級、在 `/model` 中挑選模型，或稍後恢復工作階段，被標記請求的等級就不再沿用。
* **為單一回合設定的 effort**：如果您以 `ultrathink` 提高了被標記的回合，或 skill 的 `effort` frontmatter 設定了其等級，該等級會套用於該回合。之後的回合則以 [effort 解析順序](#adjust-effort-level)為備援模型給出的等級執行。

若要查看備援後為您的工作階段設定的等級，請執行 `/effort status`。若要變更，請執行 `/effort`。

#### 檢查觸發備援的原因

備援可能在工作階段的第一個請求就觸發，甚至在您傳送任何不尋常的內容之前，因為第一個請求會攜帶工作區上下文，例如您的 CLAUDE.md 內容和 git 狀態。包含安全或生物學資料的儲存庫，光憑該上下文就可能觸發分類器。

若要檢查自訂內容是否為觸發原因，請使用 `claude --safe-mode` 啟動工作階段，這會停用 CLAUDE.md、skill、MCP 伺服器和 hook 等自訂內容。Git 狀態和目錄名稱不屬於自訂內容，仍會被包含在內。

#### 切換前先詢問

若要在每次請求被標記時自行決定如何處理，請執行 `/config`，選擇 **Switch models when a message is flagged**，然後選擇 **Ask each time**。您也可以在設定檔中將 [`switchModelsOnFlag`](https://code.claude.com/docs/zh-TW/settings-reference#switchmodelsonflag) 設為 `false`。之後，Claude Code 會在會切換模型的被標記請求處暫停，並提供兩個選項：切換至備援模型，或編輯提示詞並重試。

在互動式工作階段中，第一次有被標記的請求會切換模型時，Claude Code 可能會詢問您之後是否要自動切換。只有在您尚未設定 `switchModelsOnFlag` 時才會詢問，並會將您的選擇以該鍵儲存在您的使用者設定中。

如果您選擇改為留在目前模型，儲存的值為 `false`，與 **Ask each time** 相同。如果您關閉此詢問，Claude Code 不會儲存任何內容，並會在下次有被標記的請求會切換模型時再次詢問。

當您選擇了 **Ask each time** 時，某些情況的行為有所不同：

* 當被標記的類別沒有備援模型時（例如 Opus 5 或 Sonnet 5.5 上的生物學標記），Claude Code 不會顯示提示，請求會以拒絕結束。
* 如果兩個模型都標記同一個請求，您可以編輯提示詞並重試，或開始新的工作階段。
* 在行動應用程式上的[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)中，不支援編輯並重試。請切換模型，或從桌面瀏覽器或桌面應用程式繼續工作階段。
* 在無法顯示提示的[非互動模式](https://code.claude.com/docs/zh-TW/cli-reference.md#cli-flags)和 SDK 整合中，被標記的請求會改以拒絕結束該回合。
* 在 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md) 中，Claude Code 不會顯示提示，會切換模型的被標記請求會在備援模型上重新執行。
* 當備援目標被 [`availableModels`](#restrict-model-selection) 封鎖時，Claude Code 不會顯示提示。被標記的請求會以拒絕結束，與目標被封鎖時的自動備援相同。

#### 在 Bedrock、Agent Platform 和 Foundry 上啟用備援

在 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 和 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 上，模型 ID 是供應商專屬的，因此只有在 Claude Code 能識別所涉及的每個模型時，自動備援才會運作：

* Claude Code 必須將目前模型識別為備援來源。當模型 ID 包含 `claude-fable-5`、符合 `ANTHROPIC_DEFAULT_FABLE_MODEL` 的值，或透過 [`modelOverrides`](#override-model-ids-per-version) 對應時，Fable 5.1 和 Fable 5 會被識別。Opus 5.5、Sonnet 5.5 和 Opus 5 則透過其供應商模型 ID 或 [`modelOverrides`](#override-model-ids-per-version) 對應來識別。
* 無論拒絕的是哪個模型，Opus 目標都必須能在您的部署中解析：設定 `ANTHROPIC_DEFAULT_OPUS_MODEL`，或在供應商的模型清單中保留 Opus 4.8 項目。若兩者皆無，所有來源模型（包括 Sonnet 5.5）的備援都會維持關閉，被標記的請求會以拒絕結束。
* 被標記類別的備援模型必須能在您的部署中解析。從 Fable 模型、Opus 5.5 或 Opus 5 出發時，如果您設定了 `ANTHROPIC_DEFAULT_OPUS_MODEL`，被標記的請求會針對每個有備援的類別在該模型上重新執行；Opus 5 上的生物學標記仍會以拒絕結束。如果您未設定，被標記為網路安全的請求會在 Opus 4.8 項目上重新執行，而來自 Fable 模型或 Opus 5.5、被標記為生物學的請求則會在 Opus 5 項目上重新執行。從 Sonnet 5.5 出發時，被標記為網路安全的請求會在您於 `ANTHROPIC_DEFAULT_SONNET_MODEL` 中設定的模型上重新執行，若您未設定，則在供應商模型清單中的 Sonnet 5 項目上重新執行。

如果任一模型無法識別，Claude Code 不會切換。被標記的請求會以拒絕訊息結束，您可以使用 [`/model`](#setting-your-model) 切換模型並重試。若要讓兩個模型都能被識別，請為您的來源模型設定釘選：

* **Fable 模型**：將 `ANTHROPIC_DEFAULT_FABLE_MODEL` 設定為您的 Fable 模型 ID，讓 Claude Code 將其識別為備援來源。
* **每個來源模型**：將 `ANTHROPIC_DEFAULT_OPUS_MODEL` 設定為 Opus 模型 ID，以開啟備援並為被標記的類別提供目標。若釘選的是 Opus 家族以外的模型，或是拒絕的那個模型本身，拒絕將維持不變。
* **Sonnet 5.5**：除了 Opus 釘選外，請設定 `ANTHROPIC_DEFAULT_SONNET_MODEL`，或在供應商的模型清單中保留 Sonnet 5 項目，以提供重新執行請求的模型。若 Sonnet 釘選的是 Sonnet 家族以外的模型，或是 Sonnet 5.5 本身，拒絕將維持不變。

備援模型的上下文視窗也必須至少與工作階段的一樣大，否則 Claude Code 不會切換，被標記的請求會以相同的拒絕結束。在這些供應商上，來源模型預設以 [1M 上下文視窗](#extended-context)執行。請釘選同樣以 1M 視窗執行的模型，例如在 `ANTHROPIC_DEFAULT_OPUS_MODEL` 中釘選 Opus 4.8，或在 `ANTHROPIC_DEFAULT_SONNET_MODEL` 中釘選 Sonnet 5，並使用 Claude Code [能對應至該模型](#pin-models-for-third-party-deployments)的 ID。

#### 安全研究與生物學工作負載

攻擊性安全或生物學方面的工作負載，包括滲透測試、Capture the Flag (CTF) 練習和與生物學相關的程式碼庫，經常會觸發備援，而且通常在第一個請求就觸發。對於在 Fable 5.1、Fable 5 或 Opus 5.5 上進行的實質生物學工作，第一個會切換模型的被標記請求會將工作階段移至 Opus 5，之後被標記為生物學的請求會在那裡以拒絕結束，因為 Opus 5 沒有生物學備援。在 Opus 5 和 Sonnet 5.5 上，您從第一個被標記的請求開始就會收到這些拒絕。

這是這些領域的預期路由，而非帳戶被標記。如果您的組織需要 Fable 等級的能力來進行此類工作，請向您的 Anthropic 客戶團隊詢問受信任存取計畫。

### 調整 effort 等級

[Effort 等級](https://platform.claude.com/docs/en/build-with-claude/effort)控制自適應推理，讓模型根據任務複雜度決定是否在每個步驟思考以及思考多少。較低的 effort 對於簡單任務更快速且更便宜，而較高的 effort 則為複雜問題提供更深入的推理。

可用的 effort 等級取決於模型。未列於此處的模型不支援 effort：

| 模型 | 等級 |
| :- | :- |
| Fable 5.1 和 Fable 5 | `low`、`medium`、`high`、`xhigh`、`max` |
| Opus 5.5、Sonnet 5.5、Haiku 5.5、Opus 5、Sonnet 5、Opus 4.8 和 Opus 4.7 | `low`、`medium`、`high`、`xhigh`、`max` |
| Opus 4.6 和 Sonnet 4.6 | `low`、`medium`、`high`、`max` |

如果您設定了目前模型不支援的等級，Claude Code 會改用等於或低於您所設定等級中最高的支援等級。例如，`xhigh` 在 Opus 4.6 上會以 `high` 執行。您的組織或您自己的設定也可以限制模型提供的等級；請參閱[組織 effort 限制](#organization-effort-limits)。

Claude Code 依下列順序解析工作階段的 effort 等級，採用第一個適用的項目：

1. [`CLAUDE_CODE_EFFORT_LEVEL`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數
2. 您在工作階段中選擇的等級，例如透過 `/effort`、`/model` 選擇器或 [`applyFlagSettings()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#applyflagsettings)
3. 以 `--effort` 啟動
4. 您的設定：您為模型儲存的等級或 [`effortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#effortlevel) 鍵，兩者之間以及各設定檔之間的優先順序說明於 [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings)
5. 模型的預設 effort：所有支援 effort 的模型都預設為 `high`，但 Opus 5.5、Sonnet 5.5 和 Haiku 5.5 預設為 `medium`，Opus 4.7 預設為 `xhigh`。如果您的組織為其[組織預設模型](#organization-default-model)設定了預設 effort 等級，該等級就是您執行該模型時的預設值。

自動模型備援後適用的等級，請參閱[備援後的 effort 等級](#effort-level-after-a-fallback)。關於 subagent 和隊員，請參閱[Subagent 與隊員的 effort 等級](#effort-level-of-subagents-and-teammates)。

除非上述來源之一為 Opus 5.5 設定了等級，否則 Opus 5.5 會從 `medium` 開始，且您使用者設定檔中的頂層 `effortLevel` 不會計入 Opus 5.5。該鍵是 Claude Code 開始按模型儲存等級之前 `/effort` 寫入的舊形式：它會繼續在先前適用的地方適用，即 Opus 5、Fable 5.1 及更早的模型，而 Opus 5.5 及其後發布的模型則會從自己的預設值開始，直到您使用 `/effort` 或 `/model` 選擇器為其選擇等級為止。專案、本機或受管設定中的頂層 `effortLevel`，或透過 `--settings` 傳入的 `effortLevel`，則適用於所有模型。

當您在本機的互動式工作階段中設定 `low`、`medium`、`high` 或 `xhigh` 時，可以透過確認方式選擇其持續時間：

* 在 `/effort` 滑桿或 `/model` 選擇器中按 `Enter`，或在 `/effort` 後輸入等級：將等級儲存為您的預設值，並在之後的工作階段中套用
* 在 `/effort` 滑桿或 `/model` 選擇器中按 `s`：僅將等級套用於此工作階段。需要 Claude Code v2.1.257 或更新版本

Claude Code 會按模型儲存等級，存放在您使用者設定中的 [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings) 鍵下，因此每個模型都會保留自己儲存的等級。

`max` 是最深入的推理等級。除非您透過 `CLAUDE_CODE_EFFORT_LEVEL` 環境變數設定，否則 Claude Code 只會將 `max` 套用於目前的工作階段。

> [!NOTE]
>
> 您在透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#what-connected-devices-see) 連線的手機或瀏覽器上，從 effort 控制項選擇的等級僅適用於該工作階段。

當您在 [`-p` 執行](https://code.claude.com/docs/zh-TW/headless)中使用 `/effort` 設定等級時，Claude Code 只會將其套用於該工作階段，不會儲存為您的預設值。

`/effort` 滑桿還有一個 **Ultracode** 切換開關。Ultracode 是 Claude Code 的設定，而非模型 effort 等級：開啟時，Claude 會為實質任務協調[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)，不論工作階段以何種 effort 等級執行。關於可以持久設定它的位置，請參閱 [`ultracode`](https://code.claude.com/docs/zh-TW/settings-reference#ultracode) 設定。

使用 `/effort` 或 `ultracode` 設定開啟或關閉 ultracode 時，effort 等級不會改變。`--effort ultracode` 旗標和 Agent SDK 的 `effortLevel: "ultracode"` 值會開啟它，同時也會將等級設為 `xhigh`。在 `/effort` 滑桿或 `/model` 選擇器中挑選等級，不會改變 ultracode 的狀態。

您可以透過下列任一方式開啟 ultracode：

* **`/effort`**：執行 `/effort ultracode` 以在目前工作階段中開啟，或執行 `/effort ultracode off` 以關閉。在 `/effort` 滑桿中，按 `Tab` 切換 **Ultracode** 開關，然後按 `Enter` 套用
* **`--effort` 旗標**：使用 `claude --effort ultracode` 啟動，這會以 `xhigh` effort 並開啟 ultracode 的狀態啟動工作階段
* **`ultracode` 設定**：在設定檔中、透過 `--settings`，或在 Agent SDK 控制請求中設定 [`"ultracode": true`](https://code.claude.com/docs/zh-TW/settings-reference#ultracode)。[`applyFlagSettings()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#applyflagsettings) 請求也接受 `effortLevel: "ultracode"`，這會開啟它並將 effort 等級設為 `xhigh`

`/effort ultracode off` 形式、滑桿切換開關，以及在 `xhigh` 以外的 effort 等級保持開啟 ultracode，需要 Claude Code v2.1.284 或更新版本。在 v2.1.284 之前，開啟 ultracode 會將工作階段設為 `xhigh` effort，挑選其他等級會將其關閉，而低於 `xhigh` 的 effort 上限會使其無法使用。

將 `ultracode` 傳給 `--effort` 旗標或 Agent SDK 的 `effortLevel` 值，需要 Claude Code v2.1.203 或更新版本。在 v2.1.203 之前，`--effort ultracode` 會印出 `Unknown --effort value 'ultracode'`，且工作階段會以預設 effort 啟動。

持久化的 `effortLevel` 設定和 `CLAUDE_CODE_EFFORT_LEVEL` 環境變數不接受 `ultracode`。如果 `CLAUDE_CODE_EFFORT_LEVEL` 或 [effort 上限](#organization-effort-limits)設定了工作階段的等級，ultracode 會在該等級下保持開啟。

在下列情況下無法使用 ultracode：

* [工作流程已關閉](https://code.claude.com/docs/zh-TW/workflows.md#turn-workflows-off)
* 模型不支援 `xhigh` effort

在這些情況下，`--effort ultracode` 會以關閉 ultracode 的狀態啟動工作階段，使用模型和任何上限所允許的最高 effort 等級，最高至 `xhigh`。

#### 選擇 effort 等級

每個等級都是在 token 消耗與能力之間的取捨。預設值適合大多數程式設計任務；當您想要不同的平衡時再進行調整。

| 等級 | 使用時機 |
| :- | :- |
| `low` | 您會檢閱每個結果的快速交流，例如腦力激盪、初步草稿，或像重新命名這類的小變更 |
| `medium` | Opus 5.5、Sonnet 5.5 和 Haiku 5.5 上的預設值。在 Opus 5.5 和 Sonnet 5.5 上，適合範圍明確的日常工程工作，例如實作新功能。在預設值較高的模型上，可為能夠犧牲部分智慧的成本敏感工作減少 token 用量 |
| `high` | 需要驗證或可能出現邊緣案例的工作，例如修正現有程式碼庫中的錯誤。除 Opus 5.5、Sonnet 5.5、Haiku 5.5 和 Opus 4.7 外，所有模型的預設值 |
| `xhigh` | 以較高的 token 消耗換取更深入的推理。Opus 4.7 上的預設值 |
| `max` | 您希望 Claude 在沒有您參與的情況下處理的困難問題，例如找出安全漏洞。`max` 可能出現報酬遞減且容易過度思考，因此在廣泛採用前請先測試 |
| `ultracode` | 是 Claude Code 的設定而非等級：在任何 effort 等級下為每個實質任務規劃[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md) |

在 Opus 5.5 和 Fable 5.1 上的測試中，較高等級的 Claude 會測試更多邊緣案例，並在回答前驗證更多工作內容。它也會自行做出更多選擇。在較低等級時，Claude 會更快回傳一個起點，適合您檢閱每個結果並引導下一步的工作。若要查看相同任務在各等級下的執行情形，請閱讀部落格上的 [Using Claude Code: Spending your effort](https://claude.dev/blog/spending-your-effort/)。

effort 刻度是按模型校準的，因此相同的等級名稱在不同模型之間並不代表相同的底層數值。

Opus 5.5 [預設為 `medium`](#adjust-effort-level)，比 Opus 5 的預設值 `high` 低一個等級。在 Anthropic 的測試中，Opus 5.5 在 `medium` 下的程式設計和知識工作評估表現，與 Opus 5 在 `high` 下相當或更佳。在相同等級下，Opus 5.5 每個回合的思考量往往比 Opus 5 更多。當您從 Opus 5 移至 Opus 5.5 時，請從 `medium` 開始，而不要沿用您在 Opus 5 上使用的等級。若要針對您自己的工作測試各等級，請參閱 Opus 5.5 提示指南中的 [Calibrate effort](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5#calibrate-effort)。

#### 使用 ultrathink 進行一次性深入推理

在提示詞中的任何位置加入 `ultrathink`，即可在該回合請求更深入的推理，而不變更工作階段的 effort 設定。Claude Code 會辨識此關鍵字並加入上下文內的指示。Claude Code 會將其他片語（例如「think」、「think hard」和「think more」）當作一般提示詞文字傳遞，不會將其辨識為關鍵字。

在終端機提示詞中輸入時，此字詞也可以將該回合提高至 `xhigh` effort。當它可以這麼做時，此字詞會以彩虹色顯示。需要 Claude Code v2.1.311 或更新版本。如果您開始新回合時此字詞未以彩虹色顯示，請嘗試下列其中一項：

* 在不以 `/` 開頭的提示詞中，於引號、括號、路徑或命令等任何內容之外重新輸入它
* 如果 `CLAUDE_CODE_EFFORT_LEVEL` 設定為低於 `xhigh`，請取消設定它。或者將您自己的 [`maxEffortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#maxeffortlevel) 提高至 `xhigh` 或以上，或請組織管理員提高您的[組織限制](#organization-effort-limits)
* 在工作階段中執行 `/model` 以切換至 Opus 5.5、Sonnet 5.5、Haiku 5.5 或 Fable 5.1 模型。在此字詞無法提高回合等級的情況下（例如在 Amazon Bedrock 上），請改為[設定 effort 等級](#set-the-effort-level)

#### 設定 effort 等級

您可以透過下列任一方式變更 effort：

* **`/effort`**：不帶引數執行 `/effort` 以開啟互動式滑桿，在 `/effort` 後接等級名稱以直接設定，或執行 `/effort auto` 以清除您為目前模型儲存的等級
* **在 `/model` 中**：選擇模型時，使用左/右方向鍵調整 effort 滑桿。新等級最遲會從您的下一則訊息開始生效。在那之前，Claude 可能會繼續以舊等級工作，即使是在新模型上也一樣。當[優先順序高於您所選等級的來源](#adjust-effort-level)（例如 `CLAUDE_CODE_EFFORT_LEVEL`）適用時，Claude 會改以該來源的等級工作。
* **`--effort` 旗標**：啟動 Claude Code 時傳入等級名稱，為單一工作階段設定
* **環境變數**：將 `CLAUDE_CODE_EFFORT_LEVEL` 設定為等級名稱。若要讓 Claude Code [不傳送 effort 等級](#send-no-effort-level)，請改為將其設定為 `auto` 或 `unset`
* **設定**：在 [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings) 中設定各模型的等級，或將 [`effortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#effortlevel) 設定為 `low`、`medium`、`high` 或 `xhigh`，作為沒有設定等級之模型的預設值。這兩個鍵都不接受 `max` 作為等級，而 `ultracode` 有自己的 [`ultracode`](https://code.claude.com/docs/zh-TW/settings-reference#ultracode) 鍵
* **從已連線的裝置**：在 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md#what-connected-devices-see) 工作階段中，從手機或瀏覽器上的 effort 控制項選擇等級。該等級僅適用於目前的工作階段。需要 Claude Code v2.1.234 或更新版本
* **Skill 和 subagent frontmatter**：在 [skill](https://code.claude.com/docs/zh-TW/skills.md#frontmatter-reference) 或 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#supported-frontmatter-fields) markdown 檔案中設定 `effort`，以在該 skill 或 subagent 執行時覆寫 effort 等級

Skill 的 `effort` 會適用至其執行所在回合結束為止，或在使用 `context: fork` 時適用於分叉出的 subagent 執行期間。Subagent 的 `effort` 會在 subagent 執行期間適用，除非[其呼叫方式覆寫了它](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-an-effort-level)。當其中任一者適用時，skill 或 subagent 會以其等級執行，無論您啟動時、儲存或選擇的是哪個等級。如果設定了 `CLAUDE_CODE_EFFORT_LEVEL`，則改為套用該等級。

[`maxEffortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#maxeffortlevel) 或[組織 effort 上限](#organization-effort-limits)仍會限制 skill 或 subagent 執行時的等級。如果您在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定 `effortLevel`，Claude Code 會在 [effort 解析順序](#adjust-effort-level)的設定步驟套用它，使用者仍可使用 `/effort` 或 `--effort` 變更等級。若要讓使用者維持在某個等級或以下，請設定 [`maxEffortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#maxeffortlevel)。

#### Subagent 與隊員的 effort 等級

在主要對話的模型上，沒有自己 `effort` 的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-an-effort-level) 或[隊員](https://code.claude.com/docs/zh-TW/agent-teams.md#specify-teammates-and-models)會以您在工作階段中選擇或透過 `--effort` 設定的等級執行。在其他模型上，該等級不適用。若要選擇 subagent 的等級，請在其定義中設定 `effort`。

#### 檢查您設定的 effort 等級

選擇支援的模型時，effort 滑桿會出現在 `/model` 中。工作階段標頭中的等級（例如「with low effort」）來自您的 effort 設定，即使 Claude [仍以舊等級工作](#when-a-new-effort-level-starts)也是如此。頁尾也會在啟動時以及您變更等級時，短暫顯示為您工作階段設定的等級。

#### 新 effort 等級何時開始生效

在終端機工作階段中，一旦 `/effort` 確認新等級，您傳送的下一則訊息就會以該等級執行。您可以在進行中的回合結束後傳送，或[在 Claude 仍在工作時](https://code.claude.com/docs/zh-TW/interactive-mode.md#queue-messages-while-claude-works)傳送：

* **回合結束後**：在那之前您不需要做任何事，若該回合以舊等級完成也屬預期情況
* **Claude 仍在工作時**：輸入一則訊息，例如 `keep going`，然後按 `Enter` 將其排入佇列，而不中斷該回合。Claude 會在目前的工具呼叫完成時收到它，最遲則在回合結束時收到，並從那時起以新等級工作。

在 v2.1.242 之前，Claude Code 可能會將 `/effort` 本身排入佇列直到回合結束，而在不[擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)的工作階段中（例如在[第三方供應商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)上）則一律如此。

#### 不傳送 effort 等級

當 Claude Code 未向[支援的模型](#adjust-effort-level)傳送 effort 等級時，會套用 [API 的預設值](https://platform.claude.com/docs/en/build-with-claude/effort)，而非 Claude Code 的預設值。若要讓 Claude Code 不傳送任何等級，請從匯出 `CLAUDE_CODE_EFFORT_LEVEL` 且值為 `auto` 或 `unset`（兩者效果相同）的 shell 啟動 `claude`：

```bash theme={null}
export CLAUDE_CODE_EFFORT_LEVEL=auto
```

未傳送任何等級時，工作階段標頭和頁尾不會顯示 effort 等級。若要確認未傳送任何等級，請在 Claude Code 提示字元執行 `/effort status`：

* **`Effort level: auto`**：未傳送任何 effort 等級。
* **`Effort level: auto (currently <level>)`**：仍會傳送等級。如果低於 `max` 的 [`maxEffortLevel`](https://code.claude.com/docs/zh-TW/settings-reference#maxeffortlevel) 設定適用於目前模型，Claude Code 會傳送自己為該模型設定的預設值，並降至該上限。請移除該設定或將其設為 `max`。

> [!NOTE]
>
> 在 v2.1.304 之前，即使未傳送任何等級，`/effort status` 仍會印出 `Effort level: auto (currently high)`。

#### 自適應推理與固定思考預算

自適應推理讓每個步驟的思考變為可選，因此 Claude 能更快回應例行提示詞，並將更深入的思考保留給能從中受益的步驟。如果您希望 Claude 比目前等級產生的思考頻率更高或更低，可以直接在提示詞或 `CLAUDE.md` 中說明；模型會在其 effort 設定範圍內回應該指引。

Fable 模型、Sonnet 5 及更新版本、Haiku 5.5，以及 Opus 4.7 及更新版本一律使用自適應推理。固定思考預算模式和 `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING` 不適用於這些模型。

在 Opus 4.6 和 Sonnet 4.6 上，您可以設定 `CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING=1`，以恢復由 `MAX_THINKING_TOKENS` 控制的先前固定思考預算。請參閱[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)。

### 延伸思考

延伸思考是 Claude 在回應前產生的推理。在支援[自適應推理](#adjust-effort-level)的模型上，effort 等級是控制思考量的主要方式；下列設定用於開啟或關閉思考，並控制其顯示方式。在 Anthropic API 上關閉思考時，對於 Claude Code 已知[不接受該組合](https://code.claude.com/docs/zh-TW/errors.md#effort-isnt-available-with-thinking-turned-off)的模型（例如 Opus 5），Claude Code 會傳送 effort `high`，而非更高的等級。

| 控制項 | 設定方式 |
| :- | :- |
| 切換目前工作階段 | 在 macOS 上按 `Option+T`，在 Windows 和 Linux 上按 `Alt+T` |
| 設定全域預設值 | 執行 `/config` 並切換思考模式。儲存為 `~/.claude/settings.json` 中的 `alwaysThinkingEnabled` |
| 透過環境變數停用 | 設定 [`MAX_THINKING_TOKENS=0`](https://code.claude.com/docs/zh-TW/env-vars)，這會在 Anthropic API 上關閉思考，但 Opus 5.5、Sonnet 5.5、Haiku 5.5 和 Fable 模型除外。在[第三方供應商](https://code.claude.com/docs/zh-TW/third-party-integrations.md)上，Claude Code 會改為省略 `thinking` 參數，自適應推理模型仍可能進行思考 |

您無法在 Opus 5.5、Sonnet 5.5、Haiku 5.5 或 Fable 模型上關閉思考。對於這些模型，工作階段切換開關和 `/config` 列會顯示 `Thinking can't be turned off`，而不提供切換選項，且已儲存的 `alwaysThinkingEnabled: false` 或 `MAX_THINKING_TOKENS=0` 在這些模型上無效。在這些模型上，模型會根據 effort 等級決定每個步驟的思考量。當您切換至接受該設定的模型時，已儲存的設定會再次適用。

Claude Code 預設會收合思考輸出。按 `Ctrl+O` 切換詳細模式，即可看到以灰色斜體文字顯示的推理。Anthropic API 上的互動式工作階段預設會收到經過編修的思考區塊，因此如果您希望展開時能看到完整摘要，請在[設定](https://code.claude.com/docs/zh-TW/settings.md)中設定 `showThinkingSummaries: true`。即使思考內容被收合或編修，您仍需為所有產生的思考 token 付費。

### 延伸上下文

Fable 5.1、Fable 5、Sonnet 5 及更新版本、Haiku 5.5、Opus 4.6 及更新版本，以及 Sonnet 4.6 支援 [100 萬 token 上下文視窗](https://platform.claude.com/docs/en/build-with-claude/context-windows#context-window-sizes-by-model)，適用於處理大型程式碼庫的長時間工作階段。

Fable 5.1、Fable 5、Sonnet 5 及更新版本、Haiku 5.5，以及 Opus 4.7 及更新版本預設以 1M 視窗執行，不需要 `[1m]` 後綴。這也包括 Amazon Bedrock、Google Cloud's Agent Platform 和 Microsoft Foundry 上的工作階段，以及 [Claude apps gateway](https://code.claude.com/docs/zh-TW/claude-apps-gateway) 工作階段。若要改以 200K 視窗執行這些模型，請參閱[關閉 1M 上下文](#turn-off-1m-context)。

Opus 4.6 和 Sonnet 4.6 只能透過其 `[1m]` 變體達到 1M，而能否使用該變體取決於您的方案。在 Max、Ultra、Team 和 Enterprise 方案上（包括 Team Standard 和 Team Premium 席位），具有 1M 上下文的 Opus 4.6 已包含在您的訂閱中。具有 1M 上下文的 Sonnet 4.6 在每個訂閱方案（包括 Max 和 Ultra）上都需要[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)。

| 方案 | 具有 1M 上下文的 Opus 4.6 | 具有 1M 上下文的 Sonnet 4.6 |
| - | - | - |
| Max、Ultra、Team 和 Enterprise | 包含在訂閱中 | 需要[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans) |
| Pro | 需要[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans) | 需要[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans) |
| API 和隨用隨付 | 完整存取 | 完整存取 |

Claude Code 只有在直接連線至 Anthropic API 時才會檢查這些方案要求。如果您將 `ANTHROPIC_BASE_URL` 指向 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway#subscriptions-and-gateways)，且您已儲存的 claude.ai 登入仍是作用中的憑證，Claude Code 不會檢查您方案的用量點數。`[1m]` 選項在 `/model` 中仍可使用，由閘道決定請求是否成功。在 v2.1.229 之前，在該設定下，當 Claude Code 無法確認帳戶上的用量點數時，會拒絕 `/model sonnet[1m]`。

在 Anthropic API 上，1M 上下文視窗採用標準模型定價，超過 200K 的 token 不收取額外費用，但 Haiku 5.5 除外，其[提示詞超過 100K token 時費用較高](#haiku-5-5-context-window-and-pricing)。對於延伸上下文已包含在訂閱中的方案，用量仍由您的訂閱涵蓋。對於透過用量點數使用延伸上下文的方案，token 會計入用量點數。

#### 為 Opus 4.6 或 Sonnet 4.6 選擇 1M 上下文

若要依名稱選擇 1M 變體，請在模型別名或完整模型名稱後加上 `[1m]` 後綴：

```text theme={null}
# Append [1m] to a full model name
/model claude-opus-4-6[1m]
/model claude-sonnet-4-6[1m]

# Or to an alias: the suffix applies to the model the alias resolves to
/model opus[1m]
```

#### LLM 閘道後方的上下文視窗

如果您將 `ANTHROPIC_BASE_URL` 設定為 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)或其他代理伺服器，Claude Code 會為它能識別的每個模型提供與該模型在 Anthropic API 上相同的上下文視窗。Fable 5.1、Fable 5、Sonnet 5 及更新版本、Haiku 5.5，以及 Opus 4.7 及更新版本會取得 1M 視窗，無需選擇 `[1m]` 變體；而只能透過 `[1m]` 變體達到 1M 的模型（例如 Opus 4.6），在未使用該變體時會以 200K 執行。Claude Code 無法偵測閘道或其後方伺服器所強制執行的較低限制。如果您的閘道會拒絕超過 200K token 的請求，請在啟動 Claude Code 的環境中設定 [`CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000`](https://code.claude.com/docs/zh-TW/env-vars)，讓所有模型上的工作階段都[在該邊界進行壓縮](#set-the-auto-compact-window)。

#### 關閉 1M 上下文

若要讓工作階段維持在 200K 視窗，請在您的 shell 或[設定檔](https://code.claude.com/docs/zh-TW/env-vars.md#set-environment-variables)中設定 `CLAUDE_CODE_DISABLE_1M_CONTEXT=1`。Claude Code 會從模型選擇器中移除 `[1m]` 模型變體。對於預設以 1M 視窗執行的模型（例如 Fable 模型、Sonnet 5 及更新版本，以及 Opus 4.7 及更新版本），它也會將該模型視為具有 200K 上下文視窗：

* 開啟自動壓縮時，工作階段會透過[自動壓縮](#set-the-auto-compact-window)在 200K 邊界進行壓縮。將自動壓縮視窗設定為高於 200K 並不會解除此限制，因為 Claude Code 會將該視窗上限設為模型的上下文視窗。
* 關閉自動壓縮時，工作階段會在 200K 邊界以[上下文限制錯誤](https://code.claude.com/docs/zh-TW/errors.md#prompt-is-too-long)停止，而不是進行壓縮。

#### Haiku 5.5 上下文視窗與定價

在 Anthropic API 上，Haiku 5.5 在每個方案上都以 1M 上下文視窗執行，沒有需要選擇的 `[1m]` 後綴。其模型 ID 為 `claude-haiku-5-5`。若要使用它，請在工作階段中執行 `/model claude-haiku-5-5`，或從您的 shell 使用 `claude --model claude-haiku-5-5` 啟動 Claude Code。

當 Haiku 5.5 請求的提示詞超過 100K token 時，每個 token 的費用較高。關於兩種費率，請參閱 [Anthropic 定價](https://platform.claude.com/docs/en/about-claude/pricing)。

工作階段預設約在 967K token 時自動壓縮。若要更早壓縮，請為該模型[設定較小的自動壓縮視窗](#set-the-auto-compact-window)。

## 上下文視窗與自動壓縮

自動壓縮視窗是指上下文視窗在 Claude Code 壓縮對話之前可以填滿的程度。關於各機制在壓縮時保留與捨棄的內容，請參閱[壓縮後保留的內容](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)。

### 設定自動壓縮視窗

> [!NOTE]
>
> 若 Claude Code 針對 `CLAUDE_CODE_AUTO_COMPACT_WINDOW` 的值發出警告，請參閱[此變數的值與警告](#claude_code_auto_compact_window-values)。

您可以在下列地方設定自動壓縮視窗：

* **適用於目前模型，於本次及之後的工作階段**：執行帶有值的 `/autocompact`，例如 `/autocompact 500k`。Claude Code 會將其儲存至您的使用者設定中 [`modelSettings`](https://code.claude.com/docs/zh-TW/settings-reference#modelsettings) 下的目前模型，並套用至目前的工作階段。若受管設定等優先順序較高的[設定範圍](https://code.claude.com/docs/zh-TW/settings.md#settings-precedence)為該模型或所有模型設定了自己的視窗，該命令仍會儲存您的值，但工作階段會維持該範圍的視窗，且命令會說明此情況。執行 `/autocompact auto` 可恢復為針對您的模型調校的視窗。在 v2.1.288 之前，此命令會為所有模型儲存單一視窗，即頂層的 `autoCompactWindow`。
* **適用於所有模型**：在設定檔中設定 [`autoCompactWindow`](https://code.claude.com/docs/zh-TW/settings-reference#autocompactwindow)，例如在 `~/.claude/settings.json` 中設定 `"autoCompactWindow": 200000`。對於某個模型，您透過 `/autocompact` 為該模型儲存的視窗會優先於同一檔案中的此設定鍵。
* **適用於單次啟動**：啟動 Claude Code 時傳入 [`--autocompact`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)。此旗標會在該次啟動中覆寫您已儲存的設定，但不會變更該設定；即使您已儲存的設定有值，`claude --autocompact auto` 仍會以調校後的視窗執行工作階段。與 `/autocompact` 不同，此旗標不會被受管設定等優先順序較高的設定範圍搶先覆寫。
* **在指令碼與雲端環境中**：將 [`CLAUDE_CODE_AUTO_COMPACT_WINDOW`](https://code.claude.com/docs/zh-TW/env-vars) 設為 token 數量，例如 `200000`。除非 Claude Code [忽略該值](#claude_code_auto_compact_window-values)，否則此變數會優先於命令、旗標與 `autoCompactWindow` 設定。此時 `/autocompact` 會回報此覆寫，而不會儲存。狀態列的 `used_percentage` 是以模型的完整上下文視窗為基準計算，因此設定此變數期間，該百分比無法表示何時會執行壓縮。
* **適用於單一 subagent**：請參閱[為單一 subagent 設定自動壓縮視窗](https://code.claude.com/docs/zh-TW/sub-agents.md#subagent-auto-compact-window)。

命令與旗標接受 100K 至 1M token 的視窗大小，可使用下列任一形式：

* 單純的 token 數量，例如 `200000`
* 帶有 `k` 或 `M` 後綴，例如 `500k` 或 `1M`
* 100 至 1000 之間的純數字，代表千，因此 `200` 會設定為 200,000

無論您以何種方式設定視窗，Claude Code 都會將視窗上限設為模型的上下文視窗。

#### `CLAUDE_CODE_AUTO_COMPACT_WINDOW` 的值與警告

若警告中引用了您的 `CLAUDE_CODE_AUTO_COMPACT_WINDOW` 值，表示該值超出 100,000 至 1,000,000 的範圍，或不是 token 數量。若要停止此警告，請設定該範圍內的數字，例如 `CLAUDE_CODE_AUTO_COMPACT_WINDOW=200000`。在 Claude Code v2.1.304 或更新版本中，您也可以用 `k` 表示千、`M` 表示百萬來撰寫數字，例如 `200k` 或 `1M`。

請在第一欄中找到您警告的措辭，然後橫向查看工作階段所使用的視窗以及需要變更的項目：

| 您的警告包含 | 工作階段使用的視窗 | 需要變更的項目 |
| :- | :- | :- |
| `reads as <N> tokens, so Claude Code treats it as the 100k minimum` | 100,000 token 與您模型的上下文視窗中較小者 | 設定至少 `100000`，例如 `200000`；若您原本的 `200` 是指千，則設定為 `200k` |
| `is too large, so Claude Code treats it as the 1M maximum` | 1,000,000 token 與您模型的上下文視窗中較小者 | 您已擁有最大的視窗。若要停止此警告，請設定 `1M` 或 `1000000` |
| `isn't a usable size, so Claude Code ignores it` | 來自 `--autocompact`、`/autocompact` 或 `autoCompactWindow` 的視窗；若皆未設定，則為[預設值](#default-auto-compact-thresholds) | 設定數字，例如 `200000`，或取消設定此變數 |

沒有後綴的數字會被解讀為該數量的 token，因此即使 `/autocompact 200` 代表 200,000，`CLAUDE_CODE_AUTO_COMPACT_WINDOW=200` 仍代表 200 個 token。

### 預設自動壓縮閾值

若您未設定自動壓縮視窗，Claude Code 會在對話達到模型的上下文限制時進行壓縮，但下列工作階段除外：

* [雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)會在對話接近模型限制時進行壓縮
* 未啟用[擴充上下文](#extended-context)的 Sonnet 4.6 與 Opus 4.6 會在 200K 邊界進行壓縮
* 當您設定 [`CLAUDE_CODE_DISABLE_1M_CONTEXT=1`](https://code.claude.com/docs/zh-TW/env-vars) 時，具有原生 1M 視窗的模型（例如 Sonnet 5 與 Fable 模型）會在 200K 邊界進行壓縮
* 以原生 1M 視窗執行的模型會在視窗填滿前進行壓縮，預設約為 967K token。這些模型包括 Fable 模型、Sonnet 5 及更新版本、Haiku 5.5，以及 Opus 4.7 及更新版本。若位於自訂 `ANTHROPIC_BASE_URL` 之後，請參閱[閘道後方的上下文視窗](#context-window-behind-a-gateway)
* 使用 Claude Code 無法辨識之模型 ID（例如 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)別名）的工作階段，會在 Claude Code 為該 ID 假定的上下文視窗進行壓縮；請參閱[為閘道或自訂模型 ID 修正視窗](#correct-the-window-for-a-gateway-or-custom-model-id)

關於 Claude Code 何時也會壓縮您閒置的對話，請參閱 [`idleCompaction`](https://code.claude.com/docs/zh-TW/settings-reference#idlecompaction) 設定。

### 為閘道或自訂模型 ID 修正視窗

出現下列任一啟動警告，都表示 Claude Code 無法辨識您工作階段的模型 ID，因此無法得知該模型的上下文視窗，並假定其為 200K token：

```text theme={null}
⚠ Model "my-gateway-opus" isn't recognized · context assumed to be 200k tokens · ...
Claude Code doesn't recognize the model "my-gateway-opus", so it assumes a context window of 200k tokens. Update Claude Code, or see https://code.claude.com/docs/en/model-config#correct-the-window-for-a-gateway-or-custom-model-id to set the window.
```

Claude Code 會在假定的 200K [自動壓縮](#default-auto-compact-thresholds)對話，因此若模型的實際上下文視窗為 200K，就不需要修正。否則，請依您的 ID 選擇下列適合的方式，將實際視窗告知 Claude Code：

* **比您的 Claude Code 版本更新的模型**：在 shell 中執行 `claude update`。若更新後 Claude Code 能辨識該 ID，您就不需要再設定其他項目。
* **您的閘道或供應商為 Claude Code 已知模型所使用的名稱**：新增 [`modelOverrides`](#override-model-ids-per-version) 項目，將 Anthropic 模型 ID 對應至您的 ID，例如 `"claude-opus-4-8": "my-gateway-opus"`。您也可以改為在 [`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#fields-for-modelpicker) 列中列出您的 ID，並將 `behavesAs` 設為該模型。無論採用哪種方式，Claude Code 之後都會將該 ID 視為該模型。
* **具有 1M 視窗的模型**：在您設定模型之處，於 ID 後附加 `[1m]`，例如在 shell 中執行 `claude --model 'my-gateway-opus[1m]'`。若您已[關閉 1M 上下文](#turn-off-1m-context)，無論有無此後綴，您都會得到相同的視窗。
* **其他任何視窗**：在啟動 Claude Code 的環境中，將 [`CLAUDE_CODE_MAX_CONTEXT_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 設為以 token 計算的視窗大小，例如 `CLAUDE_CODE_MAX_CONTEXT_TOKENS=400000`。對於不以 `claude-` 開頭且沒有 `[1m]` 後綴的無法辨識 ID，此變數單獨設定即可生效。對於其他任何 ID，請先查看[它適用於哪些 ID](#which-ids-claude_code_max_context_tokens-applies-to)。

一旦 Claude Code 辨識出該 ID 或使用您提供的視窗，當您以該 ID 啟動工作階段時，就不會再出現此警告。

#### `CLAUDE_CODE_MAX_CONTEXT_TOKENS` 適用於哪些 ID

在 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)或其他自訂部署上，無論 Claude Code 是否將模型 ID 解析為 Claude 模型，它為該 ID 假定的上下文視窗都可能與模型的實際視窗不同。請將 [`CLAUDE_CODE_MAX_CONTEXT_TOKENS`](https://code.claude.com/docs/zh-TW/env-vars) 設為 Claude Code 應改為假定的視窗。

此變數如何套用取決於 ID。當 ID 不以 `claude-` 開頭（不分大小寫），或帶有 Claude Code 在讀取 ID 時會去除的後綴（例如 Google Cloud 的 Agent Platform 上使用的 `@YYYYMMDD` 日期）時，Claude Code 會將其視為供應商或自訂拼寫。在 v2.1.259 之前，Claude Code 不會計入被去除的後綴，因此帶有日期後綴且無法辨識的 `claude-` ID 會被視為單純的 `claude-` 名稱。

無法辨識的供應商或自訂拼寫、帶有 `[1m]` 的相同拼寫，以及其他所有 ID，是三種不同的情況：

* 若 Claude Code 無法將供應商或自訂拼寫解析為其可辨識的模型，且 ID 不包含 `[1m]`，則此變數會直接套用，主動壓縮會在宣告的視窗繼續進行。
* 若 Claude Code 無法將供應商或自訂拼寫解析為其可辨識的模型，且 ID 包含 `[1m]`（不分大小寫），Claude Code 會為其假定 1M 視窗，此變數單獨設定時不會套用。若要在保留主動壓縮的同時修正視窗，請一併設定 [`CLAUDE_CODE_DISABLE_1M_CONTEXT=1`](https://code.claude.com/docs/zh-TW/env-vars)。設定該變數後，Claude Code 會將此 ID 的大小視同不含 `[1m]` 的相同拼寫，因此 `CLAUDE_CODE_MAX_CONTEXT_TOKENS` 會在其適用於該未標記拼寫時套用。

  當宣告的視窗超過 200K 時，在此設定下出現[200K 限制未被強制執行](https://code.claude.com/docs/zh-TW/errors.md#the-200k-limit-isnt-enforced)的警告是預期的行為。
* 若 ID 解析為 Claude Code 可辨識的模型，或 ID 是沒有可供 Claude Code 去除之後綴的單純 `claude-` 名稱（不分大小寫），則只有在您同時設定 [`DISABLE_COMPACT`](https://code.claude.com/docs/zh-TW/env-vars)（此設定會停用所有壓縮）時，此變數才會生效。

  例如，包含 Claude Code 已知之 Claude 模型名稱的 ID，例如 `anthropic/claude-opus-4-8`、`us.anthropic.claude-…-v1:0` 或帶日期的 `claude-sonnet-4-5@20250929`，會解析為該模型。這也包括同時包含 `[1m]` 的 ID：即使設定了 `CLAUDE_CODE_DISABLE_1M_CONTEXT`，Claude Code 仍會將 `claude-opus-4-8[1m]` 解析為 Opus 4.8。

對於 Claude Code 無法辨識的模型 ID，請設定 [`CLAUDE_CODE_DISABLE_UNKNOWN_MODEL_WINDOW_ENFORCEMENT=1`](https://code.claude.com/docs/zh-TW/env-vars)，讓 Claude Code 僅在 API 以 [Claude Code 可辨識的過長錯誤](https://code.claude.com/docs/zh-TW/errors.md#prompt-is-too-long)拒絕對話後才進行壓縮。當閘道將錯誤[改寫](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md#troubleshoot-gateway-errors)為 Claude Code 無法辨識的措辭時，Claude Code 不會執行該復原程序。

## 檢查您目前的模型

您可以在兩個地方查看您目前使用的模型：

* 在[狀態行](https://code.claude.com/docs/zh-TW/statusline.md)中（如果已配置）
* 在 `/status` 中，它也會顯示您的帳戶資訊

## 新增自訂模型選項

使用 `ANTHROPIC_CUSTOM_MODEL_OPTION` 可在 `/model` 選擇器中新增單一自訂項目，而不會取代內建的別名。這對於測試 Claude Code 預設未列出的模型 ID 很有用。對於 LLM 閘道部署，當設定 `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` 時，Claude Code 可以從閘道的 `/v1/models` 端點填入選擇器，因此只有在停用探索功能，或探索未傳回您想要的模型時，才需要此變數。請參閱[閘道模型探索](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#model-discovery)。

若要改為列出多個模型，並依您自己的順序、使用您選擇的標籤，請設定 [`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#modelpicker)。其說明項目會指出當該清單取代內建清單時，選擇器會保留哪些列。

此範例設定全部三個變數，讓透過閘道路由的 Opus 部署可供選取。Claude Code 會在啟動時讀取環境變數，因此請在啟動 `claude` 之前執行這些 export 指令，或重新啟動現有的工作階段以套用它們：

```bash theme={null}
export ANTHROPIC_CUSTOM_MODEL_OPTION="my-gateway/claude-opus-5-5"
export ANTHROPIC_CUSTOM_MODEL_OPTION_NAME="Opus via Gateway"
export ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION="Custom deployment routed through the internal LLM gateway"
```

`ANTHROPIC_CUSTOM_MODEL_OPTION_NAME` 和 `ANTHROPIC_CUSTOM_MODEL_OPTION_DESCRIPTION` 為選用項目：

* 若省略名稱，當 Claude Code [識別出該 ID](#customize-pinned-model-display-and-capabilities) 時，該項目會顯示模型的名稱，否則會顯示模型 ID。
* 若省略說明，Claude Code 會使用 `Custom model (<model-id>)`。

Claude Code 會將自訂項目列在內建項目之後，而您附加的任何 [`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#modelpicker) 列則會排在其後。

Claude Code 會略過 `ANTHROPIC_CUSTOM_MODEL_OPTION` 中所設定模型 ID 的驗證，因此您可以使用 API 端點接受的任何字串。

當設定了 [`availableModels`](#restrict-model-selection) 時，也請將自訂模型 ID 加入允許清單中。否則 Claude Code 會從選擇器中過濾掉該自訂項目，並如同其他被排除的模型一樣，拒絕以 `--model` 選取它。

內嵌家族名稱的自訂 ID（例如 `my-gateway/claude-opus-5-5`）會被視為該家族的特定項目，並停用其萬用字元，因此也請列出您打算保持可選取的版本。請參閱[合併行為](#merge-behavior)。

## 環境變數

使用下列環境變數來控制別名所對應的模型名稱。每個值都必須是完整的模型名稱，或是您的 API 供應商的對等識別碼。若要選擇工作階段啟動時使用的模型，請設定 [`ANTHROPIC_DEFAULT_MODEL`](#set-a-default-model-for-new-sessions)，此表未列出該變數。

| 環境變數 | 說明 |
| - | - |
| `ANTHROPIC_DEFAULT_FABLE_MODEL` | 用於 `fable` 的模型，也是 Claude Code 在第三方供應商上為[自動模型備援](#automatic-model-fallback)識別為 Fable 模型的模型 ID |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | 用於 `opus` 的模型，或在 Plan Mode 啟用時用於 `opusplan` 的模型。 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | 用於 `sonnet` 的模型，或在 Plan Mode 未啟用時用於 `opusplan` 的模型。 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | 用於 `haiku` 或背景功能的模型 |
| `CLAUDE_CODE_SUBAGENT_MODEL` | 未以其他方式指派模型的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)、[agent team](https://code.claude.com/docs/zh-TW/agent-teams.md#specify-teammates-and-models) 隊員與[工作流程](https://code.claude.com/docs/zh-TW/workflows.md) agent 所使用的預設模型。接受 `haiku` 等別名或完整模型名稱。每次呼叫指定的模型或定義中的 `model` 欄位（包括 `inherit`）優先於此設定。若要改變此行為，請設定 [`CLAUDE_CODE_SUBAGENT_MODEL_FORCE`](https://code.claude.com/docs/zh-TW/sub-agents#run-every-subagent-on-one-model) |

在第三方供應商上，[自訂固定模型的顯示與功能](#customize-pinned-model-display-and-capabilities)說明了固定模型在 `/model` 選擇器中的該列會顯示什麼內容。

注意：`ANTHROPIC_SMALL_FAST_MODEL` 已棄用，請改用
`ANTHROPIC_DEFAULT_HAIKU_MODEL`。

### 為第三方部署固定模型

透過 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[Google Cloud's Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md)、[Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 或 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 部署 Claude Code 時，請在推出給使用者之前固定模型版本。

若未固定，Claude Code 會使用 `fable`、`opus`、`sonnet` 和 `haiku` 等模型別名，這些別名會解析為各供應商的內建預設模型 ID。該預設值可能落後於 Anthropic 的最新版本，且其指向的模型可能尚未在使用者的帳戶中啟用。當預設模型無法使用時，Amazon Bedrock 和 Google Cloud's Agent Platform 使用者會看到通知，工作階段會改用較早版本的預設模型；若預設模型為 Opus 模型且沒有可用的 Opus 版本，則會改用預設的 Sonnet 模型。Microsoft Foundry 使用者則會看到錯誤，因為 Microsoft Foundry 沒有對等的啟動檢查。

在 Amazon Bedrock 和 Google Cloud's Agent Platform 上，若使用者以特定的 Sonnet 或 Opus 版本啟動工作階段（例如透過 `--model`、`ANTHROPIC_MODEL` 或 `model` 設定），該版本會被固定為對應別名在該工作階段中的預設值：啟動檢查會略過被其取代的內建預設值，且不會顯示備援通知。在 v2.1.211 之前，即使已明確設定工作階段模型，檢查仍會執行並可能顯示通知。

> [!WARNING]
>
> 請在初始設定時將模型環境變數設定為特定的版本 ID。固定模型可讓您控制使用者何時移轉到新模型。

請針對您的供應商，搭配特定版本的模型 ID 使用下列環境變數：

| 供應商 | 範例 |
| :- | :- |
| Amazon Bedrock | `export ANTHROPIC_DEFAULT_OPUS_MODEL='us.anthropic.claude-opus-4-8'` |
| Google Cloud's Agent Platform | `export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-8'` |
| Microsoft Foundry | `export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-8'` |

對 `ANTHROPIC_DEFAULT_FABLE_MODEL`、`ANTHROPIC_DEFAULT_SONNET_MODEL` 和 `ANTHROPIC_DEFAULT_HAIKU_MODEL` 套用相同的模式。如需所有供應商目前與舊版的模型 ID，請參閱[模型概覽](https://platform.claude.com/docs/en/about-claude/models/overview)。若要將使用者升級至新的模型版本，請更新這些環境變數並重新部署。

具有原生 1M 視窗的固定模型（例如 Opus 4.8 或 Sonnet 5），在 Claude Code 能將固定的 ID 對應到該模型時，無需任何後綴即可以 [1M 上下文視窗](#extended-context)執行。當 ID 包含該模型的 Anthropic API ID（例如 `us.anthropic.claude-opus-4-8` 包含 `claude-opus-4-8`），或有 [`modelOverrides`](#override-model-ids-per-version) 項目將該模型對應到此 ID 時，即視為相符。對於 Claude Code 無法對應到任何模型的固定 ID，除非該 ID 帶有 `[1m]` 後綴，否則工作階段預設會以 200K 視窗執行。

對於透過其 `[1m]` 變體達到 1M 的模型（例如 Opus 4.6 或 Sonnet 4.6），請在 `ANTHROPIC_DEFAULT_OPUS_MODEL` 或 `ANTHROPIC_DEFAULT_SONNET_MODEL` 中的模型 ID 後方附加 `[1m]` 以啟用延伸上下文：

```bash theme={null}
export ANTHROPIC_DEFAULT_OPUS_MODEL='claude-opus-4-6[1m]'
```

加上 `[1m]` 後綴後，1M 上下文視窗會套用於該固定別名的所有使用情境，包括 [`opusplan`](#opusplan-model-setting) 的 plan mode Opus 階段，以及 `model` frontmatter 指定該別名的 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)。

* Claude Code 會在將模型 ID 傳送給您的供應商之前移除此後綴。
* 僅在底層模型[支援 1M 上下文](https://platform.claude.com/docs/en/build-with-claude/context-windows#context-window-sizes-by-model)時才附加 `[1m]`。
* 後綴是依變數讀取，而非依模型讀取。在 Amazon Bedrock、Google Cloud's Agent Platform 和 Microsoft Foundry 上，某個變數中不含 `[1m]` 的 Opus 4.6 或 Sonnet 4.6 ID 會使用 200K 上下文，即使另一個變數以後綴設定了相同的模型亦然。

當您設定 `ANTHROPIC_DEFAULT_*_MODEL` 變數時，`/model` 選擇器會以該模型的單一列取代該系列的內建列，包括所有 1M 上下文列。若要在不為該變數加上後綴的情況下使用 1M 視窗，使用者可執行 `/model opus[1m]`，Claude Code 會將後綴套用至該變數所指定的模型。`/model sonnet[1m]` 的運作方式相同。

> [!NOTE]
>
> 透過 [MDM 或受管設定檔](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)派送的 `availableModels` 允許清單在使用第三方供應商時仍然適用；[伺服器受管設定不會派送至該處](https://code.claude.com/docs/zh-TW/server-managed-settings.md#platform-availability)。
>
> 篩選會比對 `opus` 等模型別名、`claude-opus-4-8` 等版本前綴，或完整的供應商格式模型 ID。`us.anthropic.` 等供應商特定前綴不會被移除，因此若要允許特定模型，請透過 [`modelOverrides`](#override-model-ids-per-version) 進行對應，或列出其完整的供應商格式 ID：
>
> * **Google Cloud's Agent Platform**：當 Claude Code 所請求的 ID 帶有 `@` 日期（例如 `claude-sonnet-4-5@20250929`）時，請在允許清單項目中包含該日期。單獨的 `claude-sonnet-4-5` 在任一 [`availableModelsMatch`](https://code.claude.com/docs/zh-TW/settings-reference#availablemodelsmatch) 設定下都不會符合該 ID。
> * **固定模型**：列出您在該模型的 `ANTHROPIC_DEFAULT_*_MODEL` 變數中設定的值
>
> 比對前，允許清單項目與所請求模型中的任何 `[1m]` 後綴都會被移除。

### 自訂固定模型的顯示與功能

當您在第三方供應商上固定模型時，若 Claude Code 能識別固定的 ID，該模型在 `/model` 選擇器中的列預設會顯示模型名稱，否則會顯示原始 ID：

* **可識別**：Claude Code 已知模型的確切 ID，例如其 Anthropic API ID，或您的供應商或閘道所使用的對應格式，不論是否帶有 `[1m]` 後綴。固定 `us.anthropic.claude-sonnet-4-5-20250929-v1:0` 時，該列會顯示 `Sonnet 4.5`。
* **無法識別**：任何其他 ID，例如應用程式推論設定檔 ARN 或 Claude Code 不認得的模型版本，除非有 [`modelOverrides`](#override-model-ids-per-version) 項目將某個模型對應到該 ID。在 Microsoft Foundry 上，部署名稱由使用者自訂，因此無論是否有對應，Claude Code 都無法識別該處的固定 ID，該列預設會顯示部署名稱。

當某列顯示模型名稱時，其預設說明會包含固定的 ID，讓您仍能看出固定的是哪個 ID。

Claude Code 也可能無法識別固定模型支援哪些功能。您可以針對每個固定模型，使用配套的環境變數自行設定顯示名稱與說明，並宣告其功能。

這些變數在 Amazon Bedrock、Google Cloud's Agent Platform 和 Microsoft Foundry 等第三方供應商上生效。當 `ANTHROPIC_BASE_URL` 指向 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)時，`_NAME` 和 `_DESCRIPTION` 變數也會生效。直接連線至 `api.anthropic.com` 時，這些變數沒有作用。

| 環境變數 | 說明 |
| - | - |
| `ANTHROPIC_DEFAULT_OPUS_MODEL_NAME` | 固定的 Opus 模型在 `/model` 選擇器中的顯示名稱。未設定時，若 Claude Code 能識別固定的 ID，該列會顯示模型名稱，否則顯示固定的 ID |
| `ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION` | 固定的 Opus 模型在 `/model` 選擇器中的顯示說明。未設定時，該列會顯示以 `Custom Opus model` 開頭的預設說明 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES` | 固定的 Opus 模型所支援功能的逗號分隔清單 |

相同的 `_NAME`、`_DESCRIPTION` 和 `_SUPPORTED_CAPABILITIES` 後綴也可用於 `ANTHROPIC_DEFAULT_SONNET_MODEL`、`ANTHROPIC_DEFAULT_HAIKU_MODEL`、`ANTHROPIC_DEFAULT_FABLE_MODEL` 和 `ANTHROPIC_CUSTOM_MODEL_OPTION`。

Claude Code 會將模型 ID 與已知模式進行比對，以啟用 [effort 等級](#adjust-effort-level)和[延伸思考](#extended-thinking)等功能。Amazon Bedrock ARN 或自訂部署名稱等供應商特定 ID 通常不符合這些模式，導致受支援的功能維持停用。請設定 `_SUPPORTED_CAPABILITIES`，告知 Claude Code 該模型實際支援哪些功能：

| 功能值 | 啟用 |
| - | - |
| `effort` | [Effort 等級](#adjust-effort-level)與 `/effort` 命令 |
| `xhigh_effort` | `xhigh` effort 等級 |
| `max_effort` | `max` effort 等級 |
| `thinking` | [延伸思考](#extended-thinking) |
| `adaptive_thinking` | 依任務複雜度動態分配思考的自適應推理 |
| `interleaved_thinking` | 在工具呼叫之間進行思考 |

設定 `_SUPPORTED_CAPABILITIES` 後，Claude Code 會針對對應的固定模型啟用所列出的功能，並停用未列出的功能。未設定此變數時，Claude Code 會改用依模型 ID 進行的內建偵測。

此範例將 Opus 固定至 Amazon Bedrock 自訂模型 ARN、設定易於辨識的名稱，並宣告其功能：

```bash theme={null}
export ANTHROPIC_DEFAULT_OPUS_MODEL='arn:aws:bedrock:us-east-1:123456789012:custom-model/abc'
export ANTHROPIC_DEFAULT_OPUS_MODEL_NAME='Opus via Bedrock'
export ANTHROPIC_DEFAULT_OPUS_MODEL_DESCRIPTION='Opus 4.7 routed through a Bedrock custom endpoint'
export ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES='effort,xhigh_effort,max_effort,thinking,adaptive_thinking,interleaved_thinking'
```

### 依版本覆寫模型 ID

在嵌入 Claude Code 並設定 [`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST`](https://code.claude.com/docs/zh-TW/env-vars) 的平台上，主機的模型設定優先於受管模型設定，而受管的 `availableModels` 允許清單則持續有效，除非主機提供自己的允許清單；[受管設定優先順序的例外](https://code.claude.com/docs/zh-TW/settings.md#exceptions-to-managed-settings-precedence)說明了主機會覆寫哪些鍵與變數。

上述系列層級的環境變數會為每個系列別名設定一個模型 ID。若您需要將同一系列中的多個版本對應到不同的供應商 ID，請改用 `modelOverrides` 設定。

`modelOverrides` 會將個別的 Anthropic 模型 ID 對應到 Claude Code 傳送至您供應商 API 的供應商特定字串。當使用者在 `/model` 選擇器中選取已對應的模型時，Claude Code 會使用您設定的值，而非內建預設值。

這讓企業管理員能將每個模型版本路由至特定的 Amazon Bedrock 推論設定檔 ARN、Google Cloud's Agent Platform 版本名稱或 Microsoft Foundry 部署名稱，以用於治理、成本分攤或區域路由。

在您的[設定檔](https://code.claude.com/docs/zh-TW/settings.md#where-settings-live)中設定 `modelOverrides`：

```json theme={null}
{
  "modelOverrides": {
    "claude-opus-4-7": "arn:aws:bedrock:us-east-2:123456789012:application-inference-profile/opus-prod",
    "claude-opus-4-6": "arn:aws:bedrock:us-east-2:123456789012:application-inference-profile/opus-46-prod",
    "claude-sonnet-4-6": "arn:aws:bedrock:us-east-2:123456789012:application-inference-profile/sonnet-prod"
  }
}
```

鍵必須是[模型概覽](https://platform.claude.com/docs/en/about-claude/models/overview)中列出的 Anthropic 模型 ID。對於帶有日期的模型 ID，請完全依照該處所示加上日期後綴。未知的鍵會被忽略。

若要停止針對閘道別名等 ID 出現的 `[claude-code:unrecognized_model]` [診斷訊息行](https://code.claude.com/docs/zh-TW/errors.md#unrecognized-model-id-on-a-request)，請新增一個以該 ID 為值的項目。

覆寫會取代 `/model` 選擇器中每個項目背後的內建模型 ID。在 Amazon Bedrock 上，`modelOverrides` 項目優先於 Claude Code 在啟動時自動探索到的任何推論設定檔。對於已是供應商原生格式的值，例如 Amazon Bedrock 推論設定檔 ARN 或 Microsoft Foundry 部署名稱，Claude Code 會原樣傳遞給供應商。

當您透過 `--model`、`ANTHROPIC_MODEL` 環境變數或 `ANTHROPIC_DEFAULT_*_MODEL` 環境變數直接傳入 Anthropic 模型 ID 時，覆寫同樣適用。在 Amazon Bedrock、Google Cloud's Agent Platform 和 [Mantle](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint) 上，沒有 `modelOverrides` 項目的 Anthropic 模型 ID 會解析為與該版本在 `/model` 選擇器中的列相同的供應商特定 ID，前提是供應商支援該版本。Mantle 僅支援部分版本。對於不在該範圍內的 Anthropic 模型 ID，Claude Code 會將原始 ID 直接傳送至 Mantle 而不進行對應，除非有 `modelOverrides` 項目涵蓋它。在 v2.1.200 之前，`--model` 與環境變數的值會原樣傳送至供應商，不會經過覆寫對應表。

`modelOverrides` 可與 `availableModels` 搭配使用。允許清單是依據 Anthropic 模型 ID 而非覆寫值進行評估，因此即使 Opus 版本已對應到 ARN，`availableModels` 中的 `"opus"` 等項目仍會持續符合。當受管設定中設定了 `enforceAvailableModels` 時，強制執行的 Default 僅會透過來自[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md#how-claude-code-combines-managed-sources)的 `modelOverrides` 進行解析。管理員的對應（例如固定至推論設定檔 ARN 的版本）會在強制執行的 Default 中生效。來自使用者或專案設定的覆寫不會影響它。

當[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定了 `availableModels` 時，對於透過 `--model` 或上述環境變數直接傳入的 Anthropic 模型 ID，只有來自受管設定的 `modelOverrides` 會生效。對於這些 ID，Claude Code 會忽略使用者或專案設定中的覆寫，且絕不會透過任何設定來源的 `modelOverrides` 解析受管清單所排除的 ID。此受管來源限制需要 Claude Code v2.1.200 或更新版本。如需了解被封鎖的 ID 如何處理，請參閱[限制模型選擇](#restrict-model-selection)。

### 提示快取設定

Claude Code 會自動使用[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)來最佳化效能並降低成本。您可以全域停用提示快取，或針對特定模型層級停用：

| 環境變數 | 說明 |
| - | - |
| `DISABLE_PROMPT_CACHING` | 設為 `1` 可為所有模型停用提示快取。優先於各模型的設定 |
| `DISABLE_PROMPT_CACHING_HAIKU` | 設為 `1` 可為[預設 Haiku 模型](https://code.claude.com/docs/zh-TW/prompt-caching.md#disable-prompt-caching)停用提示快取 |
| `DISABLE_PROMPT_CACHING_SONNET` | 設為 `1` 可為[預設 Sonnet 模型](https://code.claude.com/docs/zh-TW/prompt-caching.md#disable-prompt-caching)停用提示快取 |
| `DISABLE_PROMPT_CACHING_OPUS` | 設為 `1` 可為[預設 Opus 模型](https://code.claude.com/docs/zh-TW/prompt-caching.md#disable-prompt-caching)停用提示快取 |
| `DISABLE_PROMPT_CACHING_FABLE` | 設為 `1` 可僅為 Fable 模型停用提示快取 |

若要分別為主要對話與 subagent 選擇快取 TTL，請參閱[自行選擇 TTL](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)。如需了解哪些情況會導致快取未命中，請參閱[Claude Code 如何使用提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)。

## 版本歷史

下表列出每個模型別名變更其所解析之模型時的 Claude Code 版本，依新到舊排列。

| 版本 | 變更 |
| :- | :- |
| v2.1.293 | 在 Anthropic API 上，`haiku` 解析為 Haiku 5.5 |
| v2.1.284 | 在 Anthropic API 上，`sonnet` 解析為 Sonnet 5.5 |
| v2.1.280 | 在 Anthropic API、Claude Platform on AWS、Amazon Bedrock 及 Google Cloud's Agent Platform 上，`opus` 解析為 Opus 5.5 |
| v2.1.257 | `fable` 解析為 Fable 5.1，但 Claude apps 閘道工作階段除外 |
| v2.1.219 | 在 Anthropic API、Claude Platform on AWS、Amazon Bedrock 及 Agent Platform 上，`opus` 解析為 Opus 5 |
| v2.1.207 | 在 Claude Platform on AWS、Amazon Bedrock 及 Agent Platform 上，`opus` 解析為 Opus 4.8 |
| v2.1.197 | 在 Anthropic API 上，`sonnet` 解析為 Sonnet 5 |
| v2.1.154 | 在 Anthropic API 上，`opus` 解析為 Opus 4.8 |
| 更早版本 | 在 Claude Platform on AWS 上，`opus` 解析為 Opus 4.7；在 Amazon Bedrock 及 Agent Platform 上則解析為 Opus 4.6。在所有供應商上，`fable` 皆解析為 Fable 5，`haiku` 皆解析為 Haiku 4.5 |

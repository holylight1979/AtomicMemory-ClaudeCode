<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/advisor | lastmod: 2026-10-21 | section: Configuration / Model and responses -->
> 來源：https://code.claude.com/docs/zh-TW/advisor（官方 zh-TW，lastmod 2026-10-21）｜分類：Configuration › Model and responses｜EN 摘要：Pair your main model with a stronger advisor model that Claude consults at key moments during a task.

# 使用顧問工具升級困難決策

> 將您的主要模型與更強大的顧問模型配對，Claude 在任務期間的關鍵時刻會諮詢該模型。

> [!NOTE]
>
> 顧問工具是實驗性功能，需要 Anthropic API。它在 Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上不可用。行為、定價和可用性可能會變更。

顧問工具讓 Claude 在任務期間的關鍵時刻諮詢第二個通常更強大的模型，例如在提交方案前、遇到重複錯誤時，或在宣佈任務完成前。顧問會收到完整的對話記錄，包括每個工具呼叫和結果，並返回 Claude 在繼續前應用的指導。

顧問在 Anthropic 基礎設施上以伺服器端方式運行，作為[伺服器工具](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool)，可供訂閱和 API 計費帳戶使用。您選擇哪個模型充當顧問，Claude 決定何時呼叫它。

本頁涵蓋如何啟用顧問、接受哪些模型配對、Claude 在諮詢期間顯示什麼，以及顧問使用如何計費。

## 何時使用顧問

顧問適合長期、多步驟的任務，其中大多數輪次是例行的，但計畫品質決定結果。範例包括大型重構、錯誤不斷重複的除錯會話，以及您希望在 Claude 宣佈完成前獨立檢查的任務。

在短期任務（幾乎沒有計畫空間）或每個輪次都需要最強模型的工作上，它的價值較少。對於這些情況，[切換主要模型](https://code.claude.com/docs/zh-TW/model-config.md#setting-your-model)，或查看[顧問與 opusplan 和子代理的比較](#compare-with-related-features)以了解獲取第二意見的其他方式。

## 啟用顧問

您可以透過三種方式設定顧問模型：

* **`/advisor` 命令**：在工作階段中途設定或變更顧問，並將其儲存為預設值
* **`advisorModel` 設定**：在您的[設定檔](https://code.claude.com/docs/zh-TW/settings.md)中配置持久預設值
* **`--advisor` 旗標**：在啟動時為單一工作階段設定顧問

這些方法中的任何一個都會為主要模型[支援它](#choose-an-advisor-model)的工作階段啟用顧問。工作階段啟動後，Claude Code 會顯示 `Advisor Tool (experimental) is on and may use more tokens · /advisor` 通知。若要停止使用顧問，請參閱[關閉顧問](#turn-the-advisor-off)。

在某些方案中，使用 Fable 作為顧問還需要您一次性[同意將 Fable 使用量計費到用量點數](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)。如需了解在您給予同意之前會發生什麼，請參閱 [Fable 顧問和用量點數](#fable-advisor-and-usage-credits)。

### 使用 `/advisor` 命令

執行 `/advisor` 而不帶引數以開啟列出可用顧問模型的選擇器，或直接傳遞模型：

```
/advisor opus
```

該命令會確認 `Advisor set to` 後跟顧問模型名稱。您的選擇會儲存到使用者設定中的 `advisorModel`，並在工作階段間保持，除了 [`advisorModel` 項目](https://code.claude.com/docs/zh-TW/settings-reference#advisormodel)列出的僅適用於目前工作階段的情況。

該命令也適用於沒有終端機選擇器的地方：在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中使用 `-p`、在 Agent SDK 中、在桌面應用程式中，以及透過 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md)。這需要 Claude Code v2.1.260 或更新版本。在這些使用介面上：

* 執行不帶引數的 `/advisor` 以列印目前的顧問模型及其接受的別名。
* 執行帶有模型的 `/advisor`，例如 `/advisor opus`，以設定它。
* 執行 `/advisor off` 以關閉它。

Claude Code 不會叫用您組織的 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 允許清單排除的已儲存顧問。若要使用顧問，請使用 `/advisor` 選擇允許的模型。

Claude Code 仍會儲存您目前主要模型不支援的顧問。該顧問會在您使用 [`/model`](https://code.claude.com/docs/zh-TW/model-config#setting-your-model) 切換到[相容的主要模型](#choose-an-advisor-model)後啟動。如果 API 已在目前對話中拒絕了已儲存的顧問，它會保持關閉狀態，直到 `/clear` 或 `/compact`，即使在您切換模型之後也是如此。

在某些方案中，使用 Fable 作為顧問還需要您一次性[同意將 Fable 使用量計費到用量點數](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)。如需了解 `/advisor fable` 在您給予同意之前會執行什麼操作，請參閱 [Fable 顧問和用量點數](#fable-advisor-and-usage-credits)。

### 在設定中設定 `advisorModel`

若要在不開啟工作階段的情況下將顧問配置為預設值，請在設定檔中設定它：

```json theme={null}
{
  "advisorModel": "opus"
}
```

### 使用 `--advisor` 旗標

若要為單一工作階段設定顧問而不變更已儲存的設定，請使用旗標啟動：

```bash theme={null}
claude --advisor opus
```

Claude Code 在該工作階段中使用旗標而不是 `advisorModel` 設定。它不會在 `claude --help` 中列出 `--advisor`。如果以下任何情況成立，Claude Code 會在啟動時以錯誤退出：

* 工作階段的主要模型不支援顧問
* 要求的模型（例如 Haiku 4.5）無法充當顧問
* 您組織的 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 允許清單排除了要求的模型
* 您要求了 Fable，而您的帳戶仍需要[用量點數同意](#fable-advisor-and-usage-credits)

如果您使用 `--advisor` 啟動[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)，且上述任何情況成立，Claude Code 會在沒有顧問的情況下啟動工作階段，而不是退出。

如果您傳遞的模型可以充當顧問，但[排名低於您的主要模型](#choose-an-advisor-model)，無論是否為背景工作階段，工作階段都會啟動。此時您的主要模型會在沒有顧問的情況下執行。

## 選擇顧問模型

Claude Code 會依據模型在顧問角色上的能力進行排名，而顧問的排名必須等於或高於您工作階段的主要模型。各列依主要模型的排名由低至高排列：

| 主要模型 | 接受的顧問 |
| - | - |
| Haiku 4.5 | Fable、Opus、Sonnet、Haiku 5.5 |
| Sonnet 4.6 | Fable、Opus、Sonnet、Haiku 5.5 |
| Opus 4.6 | Fable、Opus、Sonnet 5 或更新版本、Haiku 5.5 |
| Sonnet 5 或 Haiku 5.5 | Fable、Opus 4.7 或更新版本、Sonnet 5 或更新版本、Haiku 5.5 |
| Opus 4.7 或 Opus 4.8 | Fable、Opus 4.7 或更新版本、Sonnet 5.5 |
| Sonnet 5.5 | Fable、Opus 5 或更新版本、Sonnet 5.5 |
| Opus 5 或 Opus 5.5 | Fable、Opus 5 或更新版本 |
| Fable 5 | Fable 5.1 或 Fable 5 |
| Fable 5.1 | Fable 5.1 |

Fable 5.1 需要 Claude Code v2.1.257 或更新版本。Fable 模型需要 [Fable 存取權](https://code.claude.com/docs/zh-TW/model-config.md#work-with-fable)。以 Sonnet 5.5 作為 Opus 4.7 或 Opus 4.8 主要模型的顧問，需要 Claude Code v2.1.287 或更新版本。以 Haiku 5.5 作為主要模型或顧問，需要 Claude Code v2.1.293 或更新版本。

將顧問設定為 `fable`、`opus` 或 `sonnet`。這些別名會解析為 Claude Code 為每個模型系列[內建的預設版本](https://code.claude.com/docs/zh-TW/model-config.md#model-aliases)，會隨著新的 Claude Code 版本發佈而更新。您也可以傳遞完整的模型 ID，例如 `claude-opus-5-5` 或 `claude-haiku-5-5`。Haiku 4.5 可以呼叫顧問，但不能充當顧問。

子代理繼承已設定的顧問，並針對其自身模型應用相同的配對檢查。

Claude Code 在傳送請求前驗證配對，API 也會再次驗證：

* 對於排名低於主要模型的顧問，Claude Code 不會將其附加到主要模型的請求。`/advisor` 命令輸出和通知會顯示此情況；請參閱 [顧問的能力低於目前的主要模型](https://code.claude.com/docs/zh-TW/errors.md#advisor-is-less-capable-than-the-current-main-model)。其自身模型滿足配對的 subagent 仍可使用顧問。
* 如果 API 拒絕 Claude Code 所附加之顧問的配對，Claude Code 會在沒有顧問的情況下重新傳送該請求。對話會在沒有顧問的情況下繼續，因此您看不到錯誤，也不會獲得顧問呼叫。如果您之後使用 `/advisor` 選擇其他顧問，變更會在 `/clear` 或 `/compact` 之後以及新工作階段中生效。
* 如果主要模型或顧問是 Claude Code 無法識別的模型，顧問不會附加。

### Fable 顧問和使用額度

在某些方案中，Fable 使用會計入使用額度，Fable 作為顧問也會以相同方式計費。如果您的帳戶需要 [一次性同意將 Fable 使用計費到使用額度](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)，當您使用 `/model` 選擇 Fable 模型時，Claude Code 會要求同意，在您接受該同意之前不會將 Fable 套用為顧問。

在您接受之前，當您輸入 `/advisor fable` 或在 `/advisor` 選擇器中選擇 Fable 時，Claude Code 不會將 Fable 儲存為顧問。它會改為指向您 `/model fable`。使用 `claude --advisor fable` 時，Claude Code 會在啟動時以指向 `/model fable` 的訊息退出。在 [背景工作階段](#use-the-advisor-flag) 中，它會在沒有顧問的情況下啟動工作階段，而不是退出。如果 Fable 已儲存為您的 `advisorModel`，Claude Code 會在沒有顧問的情況下傳送請求。在其主要模型支援顧問的互動式工作階段中，它也會顯示指向 `/model fable` 的通知。

若要接受同意，請執行 `/model fable` 並選擇在 Fable 上繼續。Claude Code 會記錄同意並 [將 Fable 儲存為您選擇的模型](https://code.claude.com/docs/zh-TW/model-config.md#default-model-setting)。然後選擇 Fable 作為顧問。

### 常見模型配對

任何接受的配對都有效。這些組合以不同方式平衡成本與能力：

| 配對 | 何時使用 |
| - | - |
| Sonnet 主要 + Opus 顧問 | Sonnet 處理例行工作，並將計畫、模糊失敗和完成檢查升級到 Opus |
| Sonnet 主要 + Fable 顧問 | 在決策點獲得 Fable 指導，而無需全程執行 Fable。需要 Fable 存取權 |
| Haiku 主要 + Opus 顧問 | 具有強大計畫的最低成本主要模型。預期成本高於單獨使用 Haiku，但低於將主要模型切換到 Sonnet 或 Opus |
| Opus 主要 + Opus 顧問 | 第二個 Opus 審查第一個。適用於獨立檢查比成本更重要的高風險任務 |
| Fable 主要 + Fable 顧問 | 當 Fable 可用時的最高能力配對。Claude Code 不會將 Opus 或 Sonnet 顧問套用到 Fable 主要模型 |
| Sonnet 主要 + Sonnet 顧問 | 用於捕捉例行疏漏的較低成本第二意見 |

## Claude 何時諮詢顧問

Claude 決定何時呼叫顧問。它傾向於在提交方案前、錯誤不斷重複時以及在宣佈任務完成前進行諮詢，但時機是由模型驅動而非基於規則的。

您可以在提示中要求諮詢，就像您會要求任何工具一樣，例如 `consult the advisor before you continue`。沒有設定來限制或強制顧問呼叫；如果您希望 Claude 在任務期間更頻繁或更少地諮詢顧問，請在您的指示中說明。

## 會話期間您看到的內容

當 Claude 呼叫顧問時，文字記錄會在呼叫進行中顯示帶有顧問模型名稱的 `Advising` 行。當結果返回時，該行會報告顧問是否提供了指導：

* **Reviewed**：該行確認顧問已審查對話。當顧問返回可讀的指導時，按 `Ctrl+O` 閱讀。
* **Declined**：該行顯示 `Advisor declined to advise on this request`。如果顧問提供了原因，按 `Ctrl+O` 閱讀。
* **Unavailable**：顧問呼叫失敗，該行顯示 `Advisor unavailable (<error_code>)`，其中 `<error_code>` 是呼叫返回的代碼。

Claude 通常遵循顧問的指導，但在其自身證據與特定聲明相矛盾時進行調整：如果建議的步驟在嘗試時失敗，或檔案內容與建議相矛盾，Claude 會表面衝突而不是無條件地遵循指導。

顧問始終收到完整的對話，Claude 控制時機。如需更多控制或不同的設定，請參閱[顧問與子代理和 opusplan 的比較](#compare-with-related-features)。

## 成本

當 Claude 呼叫顧問時，顧問模型會讀取對話，因此除了主要模型的使用外，每次呼叫都會以顧問模型的費率消耗代幣。這些顧問代幣如何計費取決於您的付款方式：

* **API 計費**：您需要按顧問模型的輸入和輸出費率支付顧問代幣
* **訂閱計畫**：顧問使用計入您計畫的使用限制，除非 Fable 顧問在 Fable 使用計費的計畫上計入[使用額度](https://code.claude.com/docs/zh-TW/model-config.md#fable-and-usage-credits)

如果您的帳戶需要使用額度同意，Fable 顧問在您同意前不會計費，因為 Claude Code [在那之前不會套用選擇](#fable-advisor-and-usage-credits)。

Claude 在決策點而非每個輪次都呼叫顧問，因此將更快的主要模型與更強大的顧問配對通常比全程執行更強大的模型成本更低。顧問使用計入 [`/usage`](https://code.claude.com/docs/zh-TW/costs#track-your-costs) 顯示的會話總計。

有關顧問代幣如何在 API 回應中報告的資訊，請參閱 Claude API 文件中的[使用和計費](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool#usage-and-billing)。

## 對提示快取的影響

在會話中途啟用或停用顧問不會使主要模型的[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)失效。與[變更模型](https://code.claude.com/docs/zh-TW/prompt-caching.md#switching-models)不同，切換 `/advisor` 會保持快取的前綴完整，顧問返回的指導會在後續輪次中作為文字記錄的一部分被快取。

顧問模型自身對對話的讀取不會被快取。每個顧問呼叫都會全新處理完整的文字記錄，呼叫之間沒有重複使用。

## 需求

顧問工具需要以下所有條件：

* **僅限 Anthropic API**：顧問是伺服器執行的工具。它在 Amazon Bedrock、Claude Platform on AWS、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上不可用。透過配置有 `ANTHROPIC_BASE_URL` 的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)，可用性取決於閘道是否將請求完整轉發到 Anthropic API。如果閘道或其上游無法識別顧問工具，請參閱[自動重試和錯誤轉發](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#automatic-retry-and-error-forwarding)以了解 Claude Code 如何回應。
* **支援的主要模型**：Fable、Opus 4.6 或更新版本、Sonnet 4.6 或更新版本、Haiku 4.5，或 Haiku 5.5。請參閱[選擇顧問模型](#choose-an-advisor-model)以了解每個顧問接受的模型。
* **功能旗標擷取**：Claude Code 透過從 Anthropic 擷取的功能旗標來開啟顧問。在設定了關閉旗標擷取的變數（例如 `DISABLE_TELEMETRY`）的工作階段中，顧問保持關閉。請參閱[需要功能旗標擷取的功能](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching)。

## 關閉顧問

若要停止使用顧問，執行 `/advisor off` 或在 `/advisor` 選擇器中選擇 **No advisor**：

```
/advisor off
```

若要完全停用顧問工具，設定 `CLAUDE_CODE_DISABLE_ADVISOR_TOOL=1`。`/advisor` 命令變為無法使用，任何已設定的 `advisorModel` 都會被忽略。`--advisor` 旗標被接受但沒有效果。請參閱[環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)。

## 與相關功能的比較

顧問是結合模型優勢的幾種方式之一。根據您希望何時涉及第二個模型來選擇。

| 方法 | 更強大的模型何時執行 | 如何啟動 |
| - | - | - |
| 顧問工具 | 在任務中途的決策點 | Claude 在需要指導時呼叫它 |
| [`opusplan`](https://code.claude.com/docs/zh-TW/model-config#opusplan-model-setting) | 在計畫模式期間（當 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 允許時），然後切換到 Sonnet 以執行 | 您進入計畫模式 |
| [子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#choose-a-model)搭配 `model` 設定 | 針對整個委派的子任務 | Claude 委派，或您呼叫子代理 |
| [`/model`](https://code.claude.com/docs/zh-TW/model-config#setting-your-model) | 從下一個請求開始 | 您切換模型 |

## 另請參閱

* [模型配置](https://code.claude.com/docs/zh-TW/model-config.md)：切換模型、設定努力等級並使用 `opusplan`
* [有效管理成本](https://code.claude.com/docs/zh-TW/costs.md)：跨模型追蹤代幣使用
* [Claude API 中的顧問工具](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool)：了解基礎伺服器工具，或直接從 Messages API 使用它
* [顧問策略](https://claude.com/blog/the-advisor-strategy)：為什麼將快速主要模型與更強大的顧問配對有效

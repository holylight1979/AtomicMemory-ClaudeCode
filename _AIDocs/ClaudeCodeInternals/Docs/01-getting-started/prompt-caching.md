<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/prompt-caching | lastmod: 2026-10-29 | section: Getting started / Core concepts -->
> 來源：https://code.claude.com/docs/zh-TW/prompt-caching（官方 zh-TW，lastmod 2026-10-29）｜分類：Getting started › Core concepts｜EN 摘要：Claude Code manages prompt caching automatically. See why a model switch triggers a slow uncached turn, what `/compact` costs, why CLAUDE.md edits don't apply mid-session, and how to check your cache hit rate.

# Claude Code 如何使用 prompt caching

> Claude Code 會自動管理 prompt caching。了解為什麼模型切換會觸發緩慢的未快取回應、`/compact` 的成本、為什麼 CLAUDE.md 編輯在工作階段中途不適用，以及如何檢查您的快取命中率。

Prompt caching 讓 Claude Code 更快速且更具成本效益。沒有快取的情況下，API 會在每一回合重新處理您的完整歷史記錄。有了快取，它會重複使用已經處理過的內容，以[快取代幣費率](https://platform.claude.com/docs/en/about-claude/pricing)計費重新讀取，並且只完整處理已變更的部分。

Claude Code 會為您自動處理 prompt caching，除非您[停用它](#disable-prompt-caching)。了解 prompt caching 的運作方式仍然很有用，因為某些操作會使快取失效，並在重建時使下一個回應變得更慢且更昂貴。本頁面涵蓋哪些操作會這樣做、為什麼某些設定需要等待重新啟動才能套用，以及當使用量看起來很高時如何檢查快取效能。

## 快取的組織方式

每次您在 Claude Code 中傳送訊息時，它都會發出新的 API 請求。模型在請求之間不會記住任何內容，因此 Claude Code 會重新傳送完整的上下文：系統提示詞、您的專案上下文、每個先前的訊息和工具結果，以及您的新訊息。新內容會附加在末尾，這表示每個請求的大部分內容與前一個請求相同。提示快取是 API 避免重新處理未變更部分的方式。

API 透過將每個請求的開始部分（稱為前綴）與最近處理的內容進行比對來進行快取。在正常的回合中，前綴是整個先前的請求，只有最新的交換是新的。比對是精確的，因此前綴中任何地方的變更都會重新計算其後的所有內容。沒有按檔案或按區段的快取。請參閱 API 參考中的[提示快取如何運作](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#how-prompt-caching-works)以了解基礎機制。

![四個回合顯示為不斷增長的水平條。每個回合的請求包含前一個回合的所有內容加上末尾附加的最新交換。在第二和第三個回合中，未變更的前綴從快取中讀取，只有新的交換被處理。在第四個回合中，系統提示詞已變更，因此前綴不再比對，整個請求被重新處理並寫入。](https://mintcdn.com/claude-code/VbDJw--l6T9a9Wvm/images/prompt-caching-prefix.svg?fit=max\&auto=format\&n=VbDJw--l6T9a9Wvm\&q=85\&s=f2e8f0b8298a50305fe428ca3f1d1594)

為了充分利用前綴比對，Claude Code 會組織每個請求，使得在回合之間很少變更的內容優先出現：

| 層級 | 內容 | 變更時機 |
| - | - | - |
| 系統提示詞 | 核心指示、工具定義 | 已載入的工具定義集合變更時 |
| 專案上下文 | CLAUDE.md、自動記憶、未限定範圍的規則 | 工作階段開始時，或在 `/clear` 或 `/compact` 之後 |
| 對話 | 您的訊息、Claude 的回應、工具結果 | 每個回合 |

對對話層的變更會保留系統提示詞和專案上下文的快取。對系統提示詞的變更會使所有內容失效，因為所有後續內容現在位於不同的前綴後面。第三欄提供常見的觸發器，而不是詳盡的清單，下面的章節涵蓋完整的集合。

前綴比對規則解釋了此頁面上的大多數行為。例如，[plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 和 [skill loading](https://code.claude.com/docs/zh-TW/skills.md) 會將其指示附加為對話訊息，因此快取的前綴保持完整。

有兩個設定不會出現在層級表中，但仍會影響保留的快取內容：

* **Model**：每個模型都有自己的快取。切換模型會重新計算整個請求，即使內容相同。請參閱下面的 [Switching models](#switching-models)。
* **Effort 等級**：在大多數模型上，每個 effort 等級都有自己的快取，因此在工作階段中途變更 effort 會重新計算整個請求。在具有 API 金鑰或 Claude 訂閱的 Opus 5.5、Sonnet 5.5、Haiku 5.5 和 Fable 5.1 上，快取預設保持完整。請參閱下面的 [Changing effort level](#changing-effort-level)。

> [!TIP]
>
> 在工作階段的開始選擇您的模型和 effort 等級，然後將 `/compact` 留到任務之間的自然中斷處使用。您在任務中途進行的變更越少，快取命中率就越高。

### 快取的位置

快取發生在伺服器端，在提供您的模型的任何基礎設施中。位置取決於您的身份驗證方式：

* **API 金鑰、Claude 訂閱或 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)**：快取位於 Anthropic 的基礎設施中，透過 [Claude API](https://platform.claude.com/docs) 存取
* **Amazon Bedrock 或 Google Cloud 的 Agent Platform**：快取位於您的雲端提供者的提供基礎設施中
* **Microsoft Foundry**：取決於部署的 [hosting option](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options)。在 Azure 部署上託管的部署在 Azure 基礎設施上提供；在 Anthropic 部署上託管的部署在 Anthropic 的基礎設施上提供
* **自訂 `ANTHROPIC_BASE_URL` 或 [LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway)**：快取位於您的請求被轉發的位置，快取是否有效取決於閘道

Claude Code 也會在對話中途附加系統上下文，例如檔案變更通知，並在每個提供者和連線上標記該區塊以進行快取，除非您設定 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`](https://code.claude.com/docs/zh-TW/llm-gateway-protocol#disable-pre-release-capabilities)，在這種情況下該區塊會以未快取的方式傳送。

在提供者自己的端點、Amazon Bedrock 及其 [Mantle endpoint](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#use-the-mantle-endpoint)、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上，快取該區塊的方式與 Claude API 相同。

當您的請求通過 [LLM gateway](https://code.claude.com/docs/zh-TW/llm-gateway)、自訂 `ANTHROPIC_BASE_URL` 或雲端提供者基礎 URL 覆寫（例如 [`ANTHROPIC_BEDROCK_BASE_URL`](https://code.claude.com/docs/zh-TW/env-vars)）時，保留的快取取決於閘道如何處理 Claude Code 傳送的 [`cache_control` 標記](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#explicit-cache-breakpoints)：

* **原封不動地轉發它們**：該區塊和您的對話快取方式與在提供者自己的端點上相同。
* **以命名 `cache_control` 的 `400` 錯誤拒絕標記的請求**：Claude Code 會重新傳送請求，將標記從區塊移到您的最後一條對話訊息上，並保持在那裡，直到 Claude Code 結束為止。該區塊計費為未快取的輸入；您的對話保持快取。
* **在返回成功時移除標記**：您的整個對話歷史記錄在每個回合上計費為未快取的輸入。將區塊形式的系統內容轉換為純字串的閘道會以相同的方式丟棄標記。

有關每個提供者儲存和處理的內容，請參閱 [data usage](https://code.claude.com/docs/zh-TW/data-usage.md)。無論快取位於何處，條目在一段時間不活動後過期，下面的 [Cache lifetime](#cache-lifetime) 涵蓋 TTL 以及如何延長它。

## 使快取失效的動作

這些動作會導致下一個請求遺漏部分或全部快取。您會看到一次較慢、成本較高的回合，之後新的前綴會被快取。一旦您知道它們有成本，大多數動作在任務進行中是可以避免的。模型切換可能感覺沒有成本，直到您注意到隨後的較慢回合。

* [切換模型](#switching-models)
* [變更 effort 等級](#changing-effort-level)
* [開啟快速模式](#turning-on-fast-mode)
* [連接或移除 MCP 伺服器](#connecting-or-removing-an-mcp-server)
* [啟用或停用外掛程式](#enabling-or-disabling-a-plugin)
* [拒絕整個工具](#denying-an-entire-tool)
* [壓縮對話](#compacting-the-conversation)
* [累積許多影像](#accumulating-many-images)
* [升級 Claude Code](#upgrading-claude-code)

### 切換模型

每個模型都有自己的快取。使用 [`/model`](https://code.claude.com/docs/zh-TW/model-config#setting-your-model) 切換意味著下一個請求會讀取整個對話歷史記錄而沒有快取命中，即使內容相同。

當您在終端機執行 `/model` 時，Claude Code 會要求您確認切換，但僅限於快取仍然溫暖且新模型不是產生最後一個回應的模型時。快取在 Claude Code 在此對話中最後一次傳送請求或 Claude 最後一次回應後的一個[快取 TTL](#cache-lifetime) 內保持溫暖。一旦該時間過去，快取就會過期，因此 Claude Code 會在不詢問的情況下進行切換。

在 v2.1.238 之前，Claude Code 沒有檢查快取 TTL，即使在快取過期後也會詢問。

您也可以使用 [PreModelSwitch hook](https://code.claude.com/docs/zh-TW/hooks.md#premodelswitch-decision-control) 要求此確認或跳過它。

[`opusplan` 模型設定](https://code.claude.com/docs/zh-TW/model-config#opusplan-model-setting)在 plan mode 期間解析為 Opus，在執行期間解析為 Sonnet，因此每次 plan mode 切換都是模型切換並啟動新的快取。

[自動模型備援](https://code.claude.com/docs/zh-TW/model-config.md#automatic-model-fallback)在 Fable 模型、Opus 5.5、Sonnet 5.5 和 Opus 5 上也是模型切換。當安全分類器在具有備援模型的類別中標記請求時，Claude Code 會在該模型上重新執行請求，並且工作階段會在那裡繼續。

當 skill 或命令的 frontmatter 指定的 [`model`](https://code.claude.com/docs/zh-TW/skills#frontmatter-reference) 不同於工作階段目前模型時，該回合也是模型切換：下一個請求會讀取整個對話歷史記錄而沒有快取命中。工作階段模型會在您的下一個提示詞時恢復。`context: fork` skill 則會改為設定[分叉 subagent 的模型](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent)。

### 變更 effort 等級

在大多數模型上，在工作階段中途變更 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)意味著下一個請求會讀取整個對話歷史記錄而沒有快取命中。當快取仍然溫暖時，Claude Code 會要求您先確認變更。

在具有 API 金鑰或 Claude 訂閱的 Opus 5.5、Sonnet 5.5、Haiku 5.5 和 Fable 5.1 上，變更 effort 時會保留快取。Claude Code 會在不詢問的情況下[套用新的等級](https://code.claude.com/docs/zh-TW/model-config.md#when-a-new-effort-level-starts)。在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 [Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)上，或當您設定 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`](https://code.claude.com/docs/zh-TW/llm-gateway-protocol#disable-pre-release-capabilities) 或您的組織具有 HIPAA 設定時，其運作方式與大多數模型相同。

在 v2.1.260 之前，在具有 API 金鑰或 Claude 訂閱的 Fable 5.1 上變更 effort 也會使快取失效。

### 開啟快速模式

[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)與標準速度各自保留獨立的快取，因此在您開啟或關閉快速模式後，下一個請求無法使用另一種速度所快取的內容。在對話中第一次開啟快速模式時，下一個請求會以[快速模式費率](https://code.claude.com/docs/zh-TW/fast-mode.md#understand-the-cost-tradeoff)讀取到目前為止未經快取的整個對話。若要降低此成本，請在工作階段開始時開啟它。

* 如果您在 Claude 工作時開啟它，該回合會以標準速度完成，而任何未快取讀取的費用會在您下一個回合的第一個請求中支付。
* 如果您目前的模型不支援快速模式，啟用快速模式也會[將您切換至 Opus](https://code.claude.com/docs/zh-TW/fast-mode.md#toggle-fast-mode)。該[模型切換](#switching-models)本身會從執行中回合的下一個請求開始啟動新的快取。

之後的每次切換，都會以未快取方式讀取您所切換到的速度尚未快取的內容。Claude Code 自行進行的速度變更，例如達到速率限制後[改用標準速度](https://code.claude.com/docs/zh-TW/fast-mode.md#handle-rate-limits)以及稍後恢復快速模式，也算作切換。

### 連接或移除 MCP 伺服器

工具定義位於系統提示詞層，因此當請求中的工具定義集合在回合之間變更時，快取會失效。切換[顧問工具](https://code.claude.com/docs/zh-TW/advisor.md)是一個例外：其定義位於快取中斷點之後，因此啟用或停用 `/advisor` 會保留快取的前綴完整。[MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)變更是否執行此操作取決於[工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search)是否延遲工作階段的 MCP 工具，在支援的模型上為預設值：

* **工具延遲**：Claude Code 會為整個對話保留對話第一個請求中的工具清單，因此伺服器在工作階段中途連接或斷開不會擾亂已快取的任何內容。在第一個請求後完成連接的伺服器會提供其工具作為延遲定義，Claude 會按需載入。
* **預先載入工具**：新增定義會使快取失效，刻意移除定義也會如此。這適用於工具搜尋[已關閉或不可用](https://code.claude.com/docs/zh-TW/mcp.md#configure-tool-search)時，例如在：
  * 早於 Opus 4.5、Sonnet 4.5 和 Haiku 4.5 的 Google Cloud Agent Platform 模型上
  * Microsoft Foundry [託管於 Azure 的部署](https://platform.claude.com/docs/en/build-with-claude/claude-in-microsoft-foundry#hosting-options)上，且 Claude Code 偵測到該部署拒絕工具搜尋時

在沒有工具搜尋的情況下，工作階段中途的伺服器變更是否使快取失效取決於變更的內容。對於每個變更，此表格說明快取是否保留以及下一個請求中工具定義會發生什麼。

| 工作階段中途的變更 | 快取 | 下一個請求中的工具定義 |
| - | - | - |
| 伺服器連接，或[動態工具更新](https://code.claude.com/docs/zh-TW/mcp.md#dynamic-tool-updates)新增工具 | 已失效 | 新定義已新增 |
| 伺服器在沒有您採取任何動作的情況下斷開，例如 stdio 伺服器的程序退出 | 已保留 | 伺服器的定義保持不變。呼叫其中一個工具會傳回錯誤而不是執行，除非 Claude Code 為該次呼叫[再次啟動伺服器](https://code.claude.com/docs/zh-TW/mcp.md#stdio-servers-that-exit-or-fail-to-start) |
| 遠端伺服器在連接斷開後[自動重新連接](https://code.claude.com/docs/zh-TW/mcp.md#automatic-reconnection) | 已保留，除非在伺服器重新連接時傳送的請求新增 `WaitForMcpServers` 工具，這會使快取失效一次 | 伺服器的定義保持不變。在伺服器重新連接時傳送的請求可以在對話尚未列出時新增 `WaitForMcpServers`，然後該工具會在對話的其餘部分保持列出 |
| 您故意移除工具，例如使用[拒絕規則](#denying-an-entire-tool)或在 `/mcp` 中停用其伺服器 | 已失效 | 定義已移除 |

當您繼續其工具載入到前綴中的對話時，其中一個 MCP 伺服器仍然可以在第一個請求發出時進行連接。如果逐字稿記錄了該伺服器的工具定義，該請求會按記錄的方式包含它們，因此當伺服器以相同工具完成連接時不會變更。

編輯您的 MCP 設定本身不會變更快取。新設定只有在重新啟動後才會生效，這是伺服器連接或斷開的時候。

### 啟用或停用外掛程式

當您啟用或停用[外掛程式](https://code.claude.com/docs/zh-TW/plugins/overview.md)時，變更的成本取決於外掛程式提供的元件類型。下面的案例涵蓋每個元件類型、Claude Code 何時套用變更，以及在同一工作階段中再次停用外掛程式時會發生什麼。

#### 保留快取的外掛程式元件

Claude Code 永遠不會因外掛程式的 skill、命令、agent、hook、監視器或主題而使快取失效。它會在現有對話之後附加其內容，因此下一個請求會為該內容付費，並且仍然會從快取中讀取其之前的所有內容。

#### 提供 MCP 伺服器的外掛程式

當您啟用或停用提供 [MCP 伺服器](https://code.claude.com/docs/zh-TW/plugins/components.md#mcp-servers) 的外掛程式時，Claude Code 會遵循與[連接或移除 MCP 伺服器](#connecting-or-removing-an-mcp-server)相同的規則。

#### 程式碼智慧外掛程式

當您啟用[程式碼智慧外掛程式](https://code.claude.com/docs/zh-TW/plugins/code-intelligence.md)時，Claude 會取得 [LSP 工具](https://code.claude.com/docs/zh-TW/tools-reference.md#lsp-tool-behavior)。

#### 外掛程式變更何時套用

您在 `/plugin` 功能表中所做的變更會通過 [`/reload-plugins`](https://code.claude.com/docs/zh-TW/plugins/cli-reference#reload-plugins) 進行，Claude Code 會在您關閉功能表時為您執行。您會支付成本，無論是附加的公告還是完整重新讀取，都是在變更套用後的第一個回合。Claude Code 也可以自行套用變更：

* 對於具有 `command` 來源的外掛程式，Claude Code [可以自行重新載入外掛程式](https://code.claude.com/docs/zh-TW/plugins/loading.md#when-a-command-source-re-runs)。
* 當您[從 `/plugin` 介面安裝外掛程式](https://code.claude.com/docs/zh-TW/plugins/install#install-a-plugin)時，Claude Code 可以在安裝期間啟動它。安裝摘要會告訴您它是否執行了此操作。
* 當您在 v2.1.246 或更新版本上使用 `/cd` [移動工作階段](https://code.claude.com/docs/zh-TW/permissions.md#move-the-session-to-another-directory)時，Claude Code 會在移動過程中套用新目錄的設定啟用的外掛程式，而不會出現保留 `/reload-plugins` 的完整重新讀取警告。
* 在互動式工作階段中，當您在使用 `--plugin-dir` 傳遞的[外掛程式資料夾](https://code.claude.com/docs/zh-TW/plugins/create.md#load-a-directory-or-archive-for-one-session)中新增或移除外掛程式時，變更會立即套用。如果套用它會觸發完整重新讀取，Claude Code 會改為保留變更並顯示通知以執行 `/reload-plugins`。需要 Claude Code v2.1.265 或更新版本。

當 `/reload-plugins` 執行且重新載入會觸發完整重新讀取時，Claude Code 會顯示警告且不套用重新載入。執行 `/reload-plugins --force` 以無論如何套用它。

`/reload-plugins` 也在沒有互動式終端機的工作階段中執行，例如桌面應用程式、Agent SDK 和搭配 `-p` 的[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)，當您直接將其輸入工作階段時。需要 Claude Code v2.1.260 或更新版本。

在這些工作階段中，重新載入會套用除了外掛程式 MCP 伺服器變更之外的所有內容，這些變更[在您的下一個工作階段中生效](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#reload-plugins)，因此永遠不會在工作階段中途造成完整重新讀取的成本。

#### 您在一個工作階段中啟用然後停用的外掛程式

當您停用您在工作階段中較早啟用的外掛程式時，Claude Code 會還原先前的請求形狀。如果該前綴仍在其[快取生命週期](#cache-lifetime)內，下一個請求會讀取較舊的快取項目，而不是重建。

### 拒絕整個工具

如果您新增裸工具名稱（如 `Bash` 或 `WebFetch`）作為[拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#manage-permissions)，Claude 從您的下一個請求開始便無法呼叫該工具，無論您是通過 `/permissions` 新增規則還是通過[直接編輯設定檔](https://code.claude.com/docs/zh-TW/settings.md#when-edits-take-effect)。這包括您在回合中途通過 `/permissions` 新增的規則。

當[工具搜尋](https://code.claude.com/docs/zh-TW/mcp.md#scale-with-mcp-tool-search)處於活動狀態時（在支援的模型上為預設值），請求的工具定義不會變更，快取的前綴會保留。當工具搜尋不可用或已停用時，Claude Code 會從下一個請求中移除定義，這會使快取失效，稍後移除規則也會如此。

只有在工具名稱位置相符的拒絕規則才會以此方式封鎖工具：裸工具名稱、等效的 `Bash(*)` 形式或[工具名稱 glob](https://code.claude.com/docs/zh-TW/permissions.md#tool-name-wildcards)（如 `"*"`）。只與 MCP 工具相符的 glob（如 `"mcp__*"`）會以相同方式封鎖這些工具。範圍拒絕規則（如 `Bash(rm *)`）以及所有允許和詢問規則都不會變更 Claude 看到的工具。Claude Code 在 Claude 嘗試呼叫時檢查它們，保留前綴完整。

### 壓縮對話

[壓縮](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction)會用摘要取代您的訊息歷史記錄。根據設計，這會使對話層失效：下一個請求具有新的、較短的歷史記錄，不與舊歷史記錄共享前綴。系統提示詞層和專案上下文層可以保持快取：

* **系統提示詞**：下一個請求會從快取讀取此層，除非[繼續的對話](#resuming-a-session)保留了現已過時的系統提示詞。該對話第一次被壓縮時，Claude Code 會將其切換為目前的提示詞，下一個請求會重建此層的快取一次。
* **專案上下文**：Claude Code 會從磁碟重新載入此層。只有在工作階段開始以來 CLAUDE.md 和記憶未變更時，下一個請求才會從快取讀取它。

為了產生摘要，Claude Code 會傳送一個單獨的請求。該請求會重複您對話的系統提示詞、工具以及要摘要的歷史記錄，並以一則摘要指令作結。當快取溫暖時，該請求會從快取讀取您的前綴。因此，工作階段中途的 `/compact` 成本只是上下文大小所暗示的一小部分，並且大部分時間花在產生摘要上。

在超過[快取生命週期](#cache-lifetime)的中斷後，沒有快取可讀取，因此摘要請求會將該歷史記錄重新處理為未快取的輸入。這就是為什麼當您[繼續舊工作階段](https://code.claude.com/docs/zh-TW/sessions.md#resume-a-session)時 `/compact` 成本最高。在溫暖和冷的情況下，壓縮後的回合只會為更短的摘要重建對話快取，因此該回合不是較慢的部分。

> [!TIP]
>
> 當您捨棄的上下文是您不再需要的內容時，壓縮對您有利。為了選擇其開銷何時發生，請在工作的自然中斷處（例如任務之間）執行 `/compact`，而不是等待自動壓縮在任務中途觸發。如果您走上了想要完全放棄的路徑，請改為使用 [`/rewind`](#rewinding-the-conversation) 回到較早的回合。倒轉會截斷回到已快取的前綴，而不是像壓縮那樣建立新的前綴。

如果您讓處於[一小時 TTL](#which-ttl-each-request-gets) 的長對話閒置，Claude Code 可能會將其壓縮。若要關閉閒置壓縮，請將 [`idleCompaction`](https://code.claude.com/docs/zh-TW/settings-reference#idlecompaction) 設定為 `false`，這需要 Claude Code v2.1.290 或更新版本。

### 累積許多影像

API 限制每個請求可以攜帶多少影像和 PDF。如需目前的數字，請參閱 API 文件中的[請求限制](https://platform.claude.com/docs/en/build-with-claude/vision#request-limits)。Claude Code 也會限制請求中影像和 PDF 的總大小，因此大型螢幕擷取畫面會以比小型螢幕擷取畫面更少的影像數量達到限制。

當下一個請求會超過任一限制時，Claude Code 會從其傳送的內容中移除一批最舊的影像和 PDF，這會為更多內容騰出空間，然後才需要再次移除任何內容。Claude 無法再看到移除的影像。如果 Claude 再次需要其中一個，請再次分享它。

移除影像會變更保存它們的訊息，因此下一個請求會從這些訊息中最早的訊息開始重新處理對話。因為 Claude Code 一次移除一批，您會看到每批一個較慢的回合，而不是每個新螢幕擷取畫面一個。

### 升級 Claude Code

新的 Claude Code 版本通常會更新系統提示詞或工具定義，因此您在升級後開始的第一個對話會從頭開始建立其快取。[自動更新](https://code.claude.com/docs/zh-TW/setup.md#auto-updates)會在背景下載新版本，但在下一次啟動時套用它們，永遠不會在工作階段中途，因此您會看到這是重新啟動後的未快取第一個回合，而不是工作階段期間的意外。設定 `DISABLE_AUTOUPDATER=1` 以控制何時套用升級。

> [!NOTE]
>
> 如需繼續您在升級前開始的對話的成本，請參閱[繼續工作階段](#resuming-a-session)。

## 保留快取的動作

這些動作要麼附加到對話的末尾，要麼根本不觸及請求。其中一些動作（例如編輯 CLAUDE.md）保留快取的原因與變更在執行中的工作階段中不會生效直到 `/clear`、`/compact` 或重新啟動的原因相同。

* [編輯您的儲存庫中的檔案](#editing-files-in-your-repository)
* [在工作階段中編輯 CLAUDE.md](#editing-claude-md-mid-session)
* [變更權限模式](#changing-permission-mode)
* [變更輸出風格](#changing-output-style)
* [叫用 skill 和命令](#invoking-skills-and-commands)
* [執行 `/recap`](#running-%2Frecap)
* [倒帶對話](#rewinding-the-conversation)
* [生成 subagent](#subagents-and-the-cache)

### 編輯您的儲存庫中的檔案

檔案內容只有在 Claude 讀取時才會進入上下文，而讀取會附加到對話中。編輯 Claude 之前讀過的檔案不會追溯性地改變歷史記錄中的早期讀取。相反，Claude Code 會附加一個 [`<system-reminder>`](https://code.claude.com/docs/zh-TW/glossary#system-reminder) 注意到檔案已變更，如果需要，Claude 會重新讀取它。

### 在工作階段中編輯 CLAUDE.md

您的專案根目錄和使用者層級 CLAUDE.md 檔案在工作階段開始時讀取一次並保存在記憶體中。在工作階段中編輯它們不會使快取失效，但編輯也不會套用。Claude 繼續使用在工作階段開始時載入的版本。新內容在下一次 `/clear`、`/compact` 或重新啟動時載入。

[子目錄中的巢狀 CLAUDE.md 檔案](https://code.claude.com/docs/zh-TW/memory.md)和[具有 `paths:` frontmatter 的規則](https://code.claude.com/docs/zh-TW/memory#path-specific-rules)會在稍後視需要載入。在它載入之前自行編輯它確實會生效。載入後，內容是對話歷史記錄的一部分，因此在工作階段中編輯不會追溯性地改變它。

### 變更權限模式

在[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)之間切換，例如從手動切換到接受編輯，不會改變系統提示詞或工具定義，因此模式變更是快取安全的。例外是使用 [`opusplan`](https://code.claude.com/docs/zh-TW/model-config#opusplan-model-setting) 模型設定的 plan mode，它在您進入或離開 plan mode 時在 Opus 和 Sonnet 之間切換模型。這使得模式切換成為[模型切換](#switching-models)。

### 變更輸出風格

當您在工作階段中使用 [`/output-style`](https://code.claude.com/docs/zh-TW/output-styles#change-your-output-style)、`/config` 或 `outputStyle` 設定切換[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)時，Claude 從您的下一條訊息開始使用新風格。Claude Code 將新風格的指示作為對話中的訊息傳遞，因此該請求仍然從快取中讀取系統提示詞和較早的對話。

在 v2.1.251 之前，在工作階段中切換風格會保留快取，但在您執行 `/clear` 或開始新工作階段之前不會套用。

### 叫用 skill 和命令

[Skill](https://code.claude.com/docs/zh-TW/skills.md) 和[命令](https://code.claude.com/docs/zh-TW/commands.md)在叫用點將其指示作為使用者訊息注入。對話中較早的任何內容都不會改變。frontmatter 命名 `model` 的 skill 或命令可以是該回合的[模型切換](#switching-models)。

### 執行 `/recap`

[`/recap`](https://code.claude.com/docs/zh-TW/interactive-mode#session-recap) 生成一個摘要以在您的終端機中顯示。與 `/compact` 不同，它將摘要附加為命令輸出，而不是替換您的訊息歷史記錄，因此快取的前綴保持完整。

### 倒帶對話

[`/rewind`](https://code.claude.com/docs/zh-TW/checkpointing) 將您的對話截斷回較早的回合。剩餘的歷史記錄是快取在該點建立時的相同內容，系統提示詞和專案上下文層保持不變，因此下一個請求會命中較早的快取項目。自那時以來的每一回合都已讀過該前綴，即使原始回合比 TTL 更久遠，也保持了該項目的活躍狀態。

將檔案檢查點與對話一起還原對快取沒有單獨的影響。檔案內容只有在 Claude 讀取時才會進入上下文，與[編輯您的儲存庫中的檔案](#editing-files-in-your-repository)相同。

## 復原工作階段

當您[復原工作階段](https://code.claude.com/docs/zh-TW/sessions.md#resume-a-session)時，Claude Code 會重新傳送整個對話，而請求會從快取中讀取其前綴中未變更且仍在[快取生命週期](#cache-lifetime)內的任何部分。本頁頂部的圖層表說明每個圖層的變更內容。

系統提示會在[Claude Code 升級](#upgrading-claude-code)後或在復原時使用不同的[`--append-system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference#system-prompt-flags)文字時變更。根據預設，復原的對話會保留其開始時的系統提示，因此其歷史記錄仍位於相同提示後面，變更會在對話壓縮或新對話中生效。[復原對話中的系統提示旗標](https://code.claude.com/docs/zh-TW/cli-reference.md#system-prompt-flags-in-resumed-conversations)涵蓋 Claude Code 在每個請求上重新建置提示的情況。

## 快取生命週期

快取的前綴在一段時間的不活動後會過期。每個命中快取的請求都會重置計時器，因此只要您持續工作，快取就會保持溫暖。經過足夠長的間隔後，下一個請求會重新計算完整輸入並重新建立快取，這就是為什麼在離開後回來的第一個轉向可能會明顯變慢。

生存時間 (TTL) 控制快取存活的間隔長度。API 提供兩種：五分鐘 TTL 和[一小時 TTL](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#1-hour-cache-duration)，後者可在較長的中斷期間保持快取溫暖，但[以更高的費率計費快取寫入](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#pricing)。較長的 TTL 在您讓工作階段閒置並返回時很有幫助，因為您可以跳過過期前綴所需的重新處理。對於從不閒置超過五分鐘的短工作突發，成本更高，因為更高的寫入費率適用，而較長的快取生命週期未被使用。

### 每個請求獲得的 TTL

Claude Code 按請求決定 TTL，每個請求都屬於以下兩個固定桶之一：

* **主要對話**：您的互動式轉向、非互動式 `-p` 執行和 Agent SDK 轉向，加上 Claude Code 與它們內聯執行的幫助程式
* **其他所有內容**：Claude Code 在該對話之外進行的請求，例如[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)、[工作流程](https://code.claude.com/docs/zh-TW/workflows.md)、進程內[隊友](https://code.claude.com/docs/zh-TW/agent-teams.md)、分支、壓縮和工作階段標題

除非您自己選擇 TTL，否則 Claude Code 僅在您方案的包含使用量內的 Claude 訂閱上請求一小時 TTL。在那裡，它為主要對話請求一小時，加上 Anthropic 在伺服器端控制的一小組幫助程式請求。此表格提供兩種計費方式下每個桶的預設 TTL。

| 請求桶 | Claude 訂閱，在方案使用量內 | 使用額度、API 金鑰或雲端提供者 |
| - | - | - |
| 主要對話 | 一小時 | 五分鐘 |
| 其他所有內容 | 五分鐘，除了伺服器控制的幫助程式請求外，它們獲得一小時 | 五分鐘 |

一旦您超過方案的用量上限，Claude Code 會使用[用量點數](https://support.claude.com/en/articles/12429409-extra-usage-for-paid-claude-plans)，您將為該使用量計費，因此 Claude Code 會將主要對話降低到五分鐘 TTL，其快取寫入的計費費率較低。要在那裡保持一小時 TTL，[自己選擇 TTL](#choose-the-ttl-yourself)。

### 自己選擇 TTL

您可以為任一桶設定 TTL。每個控制項採用 `5m` 或 `1h`，Claude Code 會忽略任何其他值。

* **主要對話**：[`promptCacheTtl`](https://code.claude.com/docs/zh-TW/settings-reference#promptcachettl) 設定，或 `CLAUDE_CODE_PROMPT_CACHE_TTL` [環境變數](https://code.claude.com/docs/zh-TW/env-vars.md)
* **其他所有內容**：[`subagentPromptCacheTtl`](https://code.claude.com/docs/zh-TW/settings-reference#subagentpromptcachettl) 設定，或 `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL` 環境變數

兩個設定和兩個環境變數都需要 Claude Code v2.1.242 或更新版本。如果您使用 API 金鑰登入或使用雲端提供者，請將 `promptCacheTtl` 設定為 `1h` 以為主要對話提供一小時快取。其外的請求保持五分鐘預設值，直到您也為該桶選擇 TTL。

當多個控制項適用時，Claude Code 按此順序採用第一個匹配項：

1. `FORCE_PROMPT_CACHING_5M=1`，為兩個桶強制五分鐘
2. 桶的環境變數
3. 桶的設定
4. 對於子代理的請求，子代理的 [`experimental` frontmatter 欄位](https://code.claude.com/docs/zh-TW/sub-agents#supported-frontmatter-fields)中的 `cacheTtl` 值，需要 Claude Code v2.1.248 或更新版本。當您的 Claude 訂閱使用使用額度時，Claude Code 會忽略那裡的 `1h`
5. `ENABLE_PROMPT_CACHING_1H=1`，為兩個桶請求一小時
6. [請求桶的預設值](#which-ttl-each-request-gets)

當您調試快取行為、比較兩個 TTL 或覆蓋在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)中設定的較長 TTL 時，設定 `FORCE_PROMPT_CACHING_5M=1`。

要確認您的主要對話的快取寫入使用了哪個 TTL，請執行 `claude -p "hello" --output-format json` 並讀取結果中的 `usage.cache_creation`。Claude Code 在 `ephemeral_1h_input_tokens` 下報告一小時快取寫入，在 `ephemeral_5m_input_tokens` 下報告五分鐘快取寫入。

若要透過閘道或在 Amazon Bedrock 上取得一小時 TTL：

* **您使用 `ANTHROPIC_BASE_URL` 設定的 LLM 閘道**：部分一小時請求在 `anthropic-beta` 標頭中傳輸，因此請設定閘道以[原封不動地轉發該標頭](https://code.claude.com/docs/zh-TW/llm-gateway-protocol.md#request-headers)
* **[Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)**：請您的管理員在[閘道政策](https://code.claude.com/docs/zh-TW/claude-apps-gateway-config.md#one-hour-prompt-cache)中請求一小時 TTL
* **Amazon Bedrock**：提示快取支援、最小可快取前綴長度和一小時 TTL 可用性都因模型而異。如果快取 token 計數保持為零，請檢查 Amazon Bedrock 文件中的[支援的模型、區域和限制](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html#prompt-caching-models)。

## 快取範圍

在 Claude Code 中，快取實際上是限定在一台機器和一個目錄的範圍內。系統提示會嵌入您的自動記憶路徑，對話會以工作目錄、平台、shell 和作業系統版本的公告開始。因此在不同目錄中的兩個工作階段會建立不同的前綴並且會錯過彼此的快取。

* 您在同一目錄中並行執行的工作階段會建立相符的前綴，並可讀取彼此的快取。
* 順序工作階段只有在啟動時取得的 git 狀態快照相符時才會共享前綴，因為每個對話也會帶有該快照中的分支和最近的提交。

底層 API 快取的範圍更廣。快取在組織之間是隔離的，在某些提供者上，[在組織內的工作區之間隔離](https://platform.claude.com/docs/en/build-with-claude/prompt-caching#cache-storage-and-sharing)。在這些邊界內，兩個請求只有在其模型、[速度](#turning-on-fast-mode)和前綴皆相符時才會共享快取。

對於執行自動化程序群隊的 Agent SDK 呼叫者，請參閱[改善跨使用者和機器的提示快取](https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts.md#improve-prompt-caching-across-users-and-machines)以將自動記憶位置移出系統提示詞。

## 檢查快取效能

快取效能會在 API 對每個回應報告的兩個權杖計數中顯示。最直接的方式是使用[狀態列指令碼](https://code.claude.com/docs/zh-TW/statusline.md)來監看 `current_usage` 物件：

| 欄位 | 意義 |
| - | - |
| `cache_creation_input_tokens` | 在此輪次寫入快取的權杖，按快取寫入費率計費 |
| `cache_read_input_tokens` | 在此輪次從快取提供的權杖，按模型的[快取權杖費率](https://platform.claude.com/docs/en/about-claude/pricing)計費，低於標準輸入費率 |

高讀取與建立比率表示快取運作良好。如果建立在輪次之間保持高位，表示您的前綴中有所變更。[使快取失效的動作](#actions-that-invalidate-the-cache)章節列出常見原因。

如需每個工作階段的摘要，請執行 `/usage`。在主要對話的第一個回應之後，Claude Code 會在工作階段區塊中新增[`Prompt cache (main)` 行](https://code.claude.com/docs/zh-TW/costs#prompt-cache-statistics)，顯示工作階段的命中率、未命中計數，以及快取目前是否為熱狀態。狀態列指令碼可以從 [`prompt_cache` 物件](https://code.claude.com/docs/zh-TW/statusline#prompt-cache-fields)讀取相同的數字。兩者都需要 Claude Code v2.1.251 或更新版本。

當 Claude Code 能夠識別時，`Prompt cache (main)` 行也會命名最後一次未命中的可能原因，例如 `likely cause: tool definitions changed`。可能原因文字需要 Claude Code v2.1.260 或更新版本。

如需整個組織的可見性，OpenTelemetry 匯出器會報告每個使用者和工作階段的快取讀取和建立權杖。請參閱[監控使用情況](https://code.claude.com/docs/zh-TW/monitoring-usage.md)以取得度量和事件屬性參考。

## 子代理與快取

[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)會以自己的系統提示和工具集開始新的對話，與父代理分開。它的第一個請求不會讀取父代理的快取，因為兩個前綴不同，並且它會在自己的轉換過程中預熱自己的快取。子代理位於主對話[TTL 時間桶](#which-ttl-each-request-gets)之外，因此即使在訂閱上也能獲得五分鐘，直到您[選擇更長的時間](#choose-the-ttl-yourself)。

父代理的快取不受影響。從父代理的角度來看，子代理的呼叫和結果會附加到對話中，保持父代理的前綴完整。

相比之下，[分支](https://code.claude.com/docs/zh-TW/sub-agents.md#fork-the-current-conversation)會完全繼承父代理的系統提示、工具和對話歷史，因此它的第一個請求會讀取父代理的快取。

其他請求也可以讀取較早請求快取的前綴：

* **工作階段副本**：您[使用 `/fork` 複製的工作階段](https://code.claude.com/docs/zh-TW/agent-view#copy-the-session-with-%2Ffork)會在複製的對話末尾收到其隔離指令作為訊息，因此原始對話建立的快取保持完整。
* **壓縮**：[壓縮對話](#compacting-the-conversation)中描述的摘要化呼叫使用相同的前綴共享方法。
* **已恢復的子代理**：當 Claude [恢復子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#resume-subagents)時，已恢復執行的第一個請求可以讀取原始執行預熱的快取。
* **工作流扇出**：在[工作流扇出](https://code.claude.com/docs/zh-TW/workflows.md#prompt-caching-in-a-fan-out)中，Claude Code 預設會將除第一個代理外的所有代理保留最多 5 秒，因此它們的第一個請求可以讀取第一個代理快取的前綴。

## 停用 prompt caching

在針對特定模型或提供者除錯 caching 行為時，停用 caching 偶爾會很有用。若要將其關閉，請將以下其中一個環境變數設定為 `1`：

| 變數 | 效果 |
| - | - |
| `DISABLE_PROMPT_CACHING` | 停用所有模型的 caching |
| `DISABLE_PROMPT_CACHING_HAIKU` | 停用預設 Haiku 模型的 caching |
| `DISABLE_PROMPT_CACHING_SONNET` | 停用預設 Sonnet 模型的 caching |
| `DISABLE_PROMPT_CACHING_OPUS` | 停用預設 Opus 模型的 caching |
| `DISABLE_PROMPT_CACHING_FABLE` | 僅停用 Fable 的 caching |

`DISABLE_PROMPT_CACHING_HAIKU` 適用於預設 Haiku 模型，即 `haiku` 別名解析到的模型。它會在該模型執行的任何地方停用 caching，包括當它是您的主要模型時的主要對話。涵蓋主要對話需要 Claude Code v2.1.283 或更新版本。

該變數也涵蓋您使用已棄用的 `ANTHROPIC_SMALL_FAST_MODEL` 變數設定的背景模型，當該模型與您的主要模型不同時。

您釘選為主要模型的不同 Haiku 版本會保持 caching；請設定 `DISABLE_PROMPT_CACHING` 以停用其 caching。

`DISABLE_PROMPT_CACHING_SONNET` 和 `DISABLE_PROMPT_CACHING_OPUS` 各自適用於 `sonnet` 或 `opus` 別名解析到的模型。如果您將任何其他 Sonnet 或 Opus 模型 ID 設定為主要模型，該模型會保持 caching。例如，在 `claude-sonnet-5` 上的工作階段會保持 caching，而 `sonnet` 解析到 `claude-sonnet-5-5`。若要停用該模型的 caching，請設定 `DISABLE_PROMPT_CACHING`。

若要在整個組織中設定 caching 原則，請將這些變數或 [TTL 變數](#cache-lifetime) 中的任何一個放在[受管設定](https://code.claude.com/docs/zh-TW/managed-settings.md)的 `env` 區塊中。在正常使用時，請保持 caching 啟用。

## 相關資源

* [從建立 Claude Code 中學到的課程：Prompt caching 就是一切](https://claude.com/blog/lessons-from-building-claude-code-prompt-caching-is-everything)：Plan Mode、延遲工具加載和壓縮的設計基本原理
* [探索上下文視窗](https://code.claude.com/docs/zh-TW/context-window.md)：什麼加載到上下文以及何時加載
* [減少令牌使用](https://code.claude.com/docs/zh-TW/costs.md#reduce-token-usage)：超越快取的策略，用於管理上下文大小
* [追蹤和減少成本](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md)：Agent SDK 呼叫者的快取令牌追蹤和 TTL 配置
* [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)：基礎 API 機制、中斷點和定價

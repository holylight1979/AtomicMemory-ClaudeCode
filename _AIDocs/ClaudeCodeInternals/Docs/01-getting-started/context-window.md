<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/context-window | lastmod: 2026-10-28 | section: Getting started / Core concepts -->
> 來源：https://code.claude.com/docs/zh-TW/context-window（官方 zh-TW，lastmod 2026-10-28）｜分類：Getting started › Core concepts｜EN 摘要：An interactive simulation of how Claude Code's context window fills during a session. See what loads automatically, what each file read costs, and when rules and hooks fire.

# 探索上下文視窗

> Claude Code 上下文視窗在會話期間如何填充的互動模擬。查看自動加載的內容、每個文件讀取的成本，以及規則和 hooks 何時觸發。

Claude Code 的上下文視窗包含 Claude 對您的會話所知的一切：您的指令、它讀取的文件、它自己的回應，以及從不在您的終端中出現的內容。下面的時間線播放了從啟動到壓縮的完整會話：在您輸入任何內容之前加載的內容、每個文件讀取、規則和 hook 在 Claude 工作時添加的內容，以及子代理如何將大型讀取保持在上下文之外。請參閱[書面分解](#what-the-timeline-shows)以獲取相同內容的列表形式。

## 時間軸顯示的內容

該工作階段展示了一個現實的流程，包含代表性的權杖計數：

* **在您輸入任何內容之前**：CLAUDE.md、自動記憶、MCP 工具名稱和 skill 描述都會載入到上下文中。[AGENTS.md 檔案](https://code.claude.com/docs/zh-TW/memory.md#agents-md)可以取代 CLAUDE.md 載入。您自己的設定可能會在此處添加更多內容，例如[輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md)或來自 [`--append-system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference) 的文字。
* **當 Claude 工作時**：每次檔案讀取都會增加上下文，[路徑範圍規則](https://code.claude.com/docs/zh-TW/memory.md#path-specific-rules)會自動與匹配的檔案一起載入，並且[PostToolUse hook](https://code.claude.com/docs/zh-TW/hooks-guide.md) 會在每次編輯後觸發。
* **後續提示**：[子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)在其自己的獨立上下文視窗中處理研究，因此大型檔案讀取不會進入您的視窗。只有摘要和一個小的中繼資料預告片會返回。
* **在逐步解說的最後**：您執行 `/compact`，它會將對話替換為結構化摘要。大多數啟動內容會自動重新載入；下表顯示每個機制會發生什麼。

## 壓縮後保留的內容

當長時間的工作階段進行壓縮時，Claude Code 會總結對話歷史以適應上下文視窗。自 v2.1.198 起，總結請求會繼承您工作階段的[延伸思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)設定，因此當您的工作階段啟用思考時，它會在啟用思考的情況下進行推理，否則保持關閉。思考只會影響摘要的生成方式；您的工作階段設定在之後保持不變。每種內容發生的情況取決於它的載入方式：

| 機制 | 壓縮後 |
| :- | :- |
| 系統提示詞和輸出風格 | 兩者仍然適用 |
| 專案根目錄 CLAUDE.md 和未限定範圍的規則 | 從磁碟重新注入 |
| 自動記憶 | 從磁碟重新注入 |
| Skill 描述 | 根據您目前的 [skill](https://code.claude.com/docs/zh-TW/skills.md) 重新建構並重新注入。需要 Claude Code v2.1.304 或更新版本 |
| [Git 狀態快照](https://code.claude.com/docs/zh-TW/settings-reference.md#includegitinstructions) | 如果工作階段開始時有快照，Claude Code 會從您的儲存庫讀取新的快照 |
| Claude 在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 中編寫的計畫 | 從磁碟重新注入 |
| 具有 `paths:` frontmatter 的規則 | Claude Code [視需要](https://code.claude.com/docs/zh-TW/memory.md#path-specific-rules)重新載入它們 |
| 子目錄中的巢狀 CLAUDE.md | Claude Code [視需要](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load)重新載入它們 |
| Claude 讀取或編輯的檔案 | Claude Code 重新讀取最多五個，最近修改的優先 |
| 已叫用的 skill 主體 | 重新注入，每個 skill 上限為 5,000 個 token，總計 25,000 個 token；最舊的優先刪除 |
| [背景命令](https://code.claude.com/docs/zh-TW/interactive-mode.md#background-bash-commands)和背景 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background) | 保持執行。Claude Code 提醒 Claude 哪些仍在執行，以便它不會啟動重複的 |
| hook 較早新增的上下文 | 與其餘對話一起總結 |
| 符合 `compact` 來源的 [SessionStart hook](https://code.claude.com/docs/zh-TW/hooks-guide.md#re-inject-context-after-compaction) | Claude Code 執行它們並將其輸出新增到壓縮的上下文中 |

壓縮後立即，Claude Code 重新讀取 Claude 在工作階段中讀取或編輯的最多五個檔案，選擇最近修改的檔案。超過 5,000 個 token 的檔案會以路徑參考的形式返回，不含其內容，顯示為 `Referenced file` 而不是 `Read`。

路徑限定範圍的規則和巢狀 CLAUDE.md 檔案在 Claude 讀取、寫入或編輯其觸發檔案時載入到訊息歷史記錄中，因此壓縮會將它們與其他所有內容一起總結。如果規則必須在壓縮後保持，請刪除 `paths:` frontmatter 或將其移至專案根目錄 CLAUDE.md。

skill 主體在壓縮後重新注入，但大型 skill 會被截斷以適應每個 skill 的上限，一旦超過總預算，最舊的已叫用 skill 就會被刪除。截斷會保留檔案的開頭，因此請將最重要的指示放在 `SKILL.md` 的頂部附近。

## 當上下文填滿時

Claude Code 會在接近上限時自動壓縮，因此上下文視窗填滿並不會結束您的工作階段。自動壓縮的運作方式與時間軸中的 `/compact` 步驟相同。請參閱[當上下文填滿時](https://code.claude.com/docs/zh-TW/how-claude-code-works.md#when-context-fills-up)，了解它會保留哪些內容。若想了解 Claude Code 何時也會壓縮您閒置的對話，請參閱[閒置壓縮](https://code.claude.com/docs/zh-TW/settings-reference.md#idlecompaction)。

您也可以在自動壓縮執行之前採取行動：

* **依指定重點壓縮**：在開始冗長的新任務之前，執行附帶指令的 `/compact`，例如 `/compact focus on the auth bug fix`。摘要會保留您選擇的內容，而不是自動壓縮所推測的重要內容。
* **壓縮部分對話**：執行 `/rewind`，選取一則訊息，然後選擇 **Summarize from here** 或 **Summarize up to here**。請參閱[倒轉與摘要](https://code.claude.com/docs/zh-TW/checkpointing.md#rewind-and-summarize)，了解每個選項會保留哪些內容，以及如何引導摘要。
* **提早壓縮**：執行附帶 token 數量的 [`/autocompact`](https://code.claude.com/docs/zh-TW/commands#all-commands)，例如 `/autocompact 500k`，以設定上下文視窗填滿到何種程度時執行自動壓縮。請參閱[設定自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)，了解可接受的值與覆寫方式。
* **在任務之間清除**：切換到不相關的工作時執行 `/clear`。舊的對話會排擠您接下來需要的檔案，而且每則訊息都會耗用 token。
* **委派大量讀取**：將研究工作交給 [subagent](https://code.claude.com/docs/zh-TW/sub-agents.md)，讓檔案內容保留在它的上下文視窗中，而非您的上下文視窗。

如果您需要更大的視窗而非更精簡的對話，Fable 模型、Sonnet 5 及更新版本、Haiku 5.5、Opus 4.6 及更新版本，以及 Sonnet 4.6 皆支援 100 萬 token 的上下文視窗。請參閱[延伸上下文](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)，了解各方案的可用性，以及如何選取 `[1m]` 模型變體。在較大的上限下，壓縮的運作方式相同。

自動壓縮的執行時機取決於您的模型與設定。請參閱[預設自動壓縮閾值](https://code.claude.com/docs/zh-TW/model-config.md#default-auto-compact-thresholds)，了解各模型的界限；若 Claude Code 對您的模型 ID（例如 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)別名）假設了錯誤的視窗，請參閱[為閘道或自訂模型 ID 修正視窗](https://code.claude.com/docs/zh-TW/model-config.md#correct-the-window-for-a-gateway-or-custom-model-id)。

## 檢查您自己的會話

該可視化使用代表性數字。要在任何時刻查看您的實際上下文使用情況，請運行 `/context` 以獲取按類別的實時分解和優化建議，包括加載了哪些 CLAUDE.md 和自動記憶文件。運行 `/memory` 以開啟和編輯這些文件。

## 相關資源

有關時間線中顯示的功能的更深入覆蓋，請參閱這些頁面：

* [擴展 Claude Code](https://code.claude.com/docs/zh-TW/features-overview.md)：何時使用 CLAUDE.md 與技能與規則與 hooks 與 MCP
* [存儲指令和記憶](https://code.claude.com/docs/zh-TW/memory.md)：CLAUDE.md 層次結構和自動記憶
* [子代理](https://code.claude.com/docs/zh-TW/sub-agents.md)：將研究委託給單獨的上下文視窗
* [最佳實踐](https://code.claude.com/docs/zh-TW/best-practices.md#keep-cost-and-context-down)：讓工作階段保持專注並降低成本
* [提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md)：哪些操作會使緩存的前綴失效
* [減少令牌使用](https://code.claude.com/docs/zh-TW/costs.md#reduce-token-usage)：保持上下文使用低的策略

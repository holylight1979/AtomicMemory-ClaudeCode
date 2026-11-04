<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/sub-agents | lastmod: 2026-11-03 | section: Build with Claude Code / Agents and parallel work -->
> 來源：https://code.claude.com/docs/zh-TW/sub-agents（官方 zh-TW，lastmod 2026-11-03）｜分類：Build with Claude Code › Agents and parallel work｜EN 摘要：Create and use specialized AI subagents in Claude Code for task-specific workflows and improved context management.

# 建立自訂 subagents

> 在 Claude Code 中建立和使用專門的 AI subagents，用於特定任務的工作流程和改進的上下文管理。

Subagents 是專門的 AI 助手，用於處理特定類型的任務。當側面任務會用搜尋結果、日誌或檔案內容淹沒您的主要對話時，請使用一個 subagent，而您不會再次參考這些內容：subagent 在自己的上下文中執行該工作，並僅返回摘要。當您持續產生相同類型的工作者並使用相同指令時，定義自訂 subagent。

每個 subagent 在自己的 context window 中執行，具有自訂系統提示、特定工具存取和獨立權限。它也會傳送自己的請求，這些請求計入與您的主要對話相同的[使用限制](https://code.claude.com/docs/zh-TW/costs.md#plan-usage-breakdown)。當 Claude 遇到與 subagent 描述相符的任務時，它會委派給該 subagent，該 subagent 獨立工作並返回結果。若要在實踐中查看上下文節省，[context window visualization](https://code.claude.com/docs/zh-TW/context-window.md) 會逐步說明一個 subagent 在自己的獨立視窗中處理研究的工作階段。

> [!NOTE]
>
> Subagents 在單一工作階段內工作。若要執行許多獨立工作階段並行並從一個地方監控它們，請參閱 [background agents](https://code.claude.com/docs/zh-TW/agent-view.md)。對於相互通訊的工作階段，請參閱 [cross-session messaging](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)。對於 Claude 產生和監督的協調團隊工作階段，請參閱 [agent teams](https://code.claude.com/docs/zh-TW/agent-teams.md)。

Subagents 可以幫助您：

* **保留上下文**，將探索和實現保持在主要對話之外
* **強制執行約束**，限制 subagent 可以使用的工具
* **跨專案重複使用配置**，使用使用者層級的 subagents
* **專門化行為**，針對特定領域使用專注的系統提示
* **控制成本**，將任務路由到更快、更便宜的模型，如 Haiku

Claude 使用每個 subagent 的描述來決定何時委派任務。當您建立 subagent 時，請寫一個清晰的描述，以便 Claude 知道何時使用它。

這些描述會佔用上下文，因此請保持簡短。當您的 subagents（除了內建的 subagents 外）的合併描述超過 15,000 個 tokens 時，Claude Code 會在啟動時顯示 [警告，並顯示總 token 計數](https://code.claude.com/docs/zh-TW/errors.md#agent-descriptions-are-over-the-15000-token-limit)。修剪您的 subagents 的 `description` 欄位，並將詳細資訊移至每個 subagent 的系統提示中，該提示僅在該 subagent 執行時載入。

## 內建 subagents

Claude Code 包括內建 subagents，Claude 在適當時會自動使用。每個都繼承父對話的權限規則；大多數以受限的工具集執行。

Explore 和 Plan 啟動時不會載入您的 CLAUDE.md 檔案和 git status 快照，以保持研究快速且經濟高效。其他內建和[自訂 subagent](#configure-subagents) 都會載入兩者，除非您在自訂 subagent 的定義中設定 [`omitClaudeMd`](#supported-frontmatter-fields)，使其啟動時不載入使用者、專案和本機 CLAUDE.md 檔案。如需了解到達 subagent 的完整詳細資訊，請參閱[啟動時載入的內容](#what-loads-at-startup)。

> [tab] Explore
>
> 一個快速、唯讀的代理，針對搜尋和分析程式碼庫進行最佳化。
>
> * **Model**：主要對話的模型。當主要對話在 Fable 上執行時，Explore 的模型取決於您的連線方式：
>   * 使用 Claude 訂閱、Anthropic Console 帳戶，或透過 `ANTHROPIC_BASE_URL` 連線的 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway)時，Explore 會在 [`opus` 別名](https://code.claude.com/docs/zh-TW/model-config#model-aliases)所解析的 Opus 模型上執行。
>   * 在 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry、[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 或 [Claude apps 閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway)上，Explore 會維持使用主要對話的模型。
> * **Tools**：唯讀工具；Write 和 Edit 被拒絕
> * **Purpose**：檔案發現、程式碼搜尋、程式碼庫探索
>
> 一個名為 `Explore` 的[使用者或專案 subagent](#choose-the-subagent-scope) 會覆寫內建的，並保留其自己的 `model` 欄位，因此定義一個具有 `model: haiku` 的 subagent，即可在較低成本的模型上執行探索。若要將單一模型強制套用至每個 subagent（包括 Explore），請參閱[在一個模型上執行每個 subagent](#run-every-subagent-on-one-model)。
>
> 當 Claude 需要搜尋或理解程式碼庫而不進行更改時，它會委派給 Explore。這樣可以將探索結果保持在主要對話上下文之外。
>
> 當呼叫 Explore 時，Claude 指定一個徹底程度：**quick** 用於目標查詢，**medium** 用於平衡探索，或 **very thorough** 用於全面分析。

> [tab] Plan
>
> 一個研究代理，在 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode) 期間使用，以在呈現計畫之前收集上下文。
>
> * **Model**：繼承自主要對話，除非您設定 `CLAUDE_CODE_SUBAGENT_MODEL` 並[強制將其套用至每個 subagent](#run-every-subagent-on-one-model)
> * **Tools**：唯讀工具；Write 和 Edit 被拒絕
> * **Purpose**：用於規劃的程式碼庫研究
>
> 當您處於 plan mode 且 Claude 需要理解您的程式碼庫時，它會將研究委派給 Plan subagent，以便探索輸出保持在單獨的上下文視窗中，而主要對話保持唯讀。

> [tab] General-purpose
>
> 一個能力強大的代理，用於需要探索和行動的複雜多步驟任務。
>
> * **Model**：如果您設定了 [`CLAUDE_CODE_SUBAGENT_MODEL`](#choose-a-model) 模型且沒有其他方式指派模型，則為該模型，否則為主要對話的模型；[選擇模型](#choose-a-model)說明完整順序，[在一個模型上執行每個 subagent](#run-every-subagent-on-one-model) 展示如何讓變數覆蓋這些來源
> * **Tools**：[可供 subagents 使用](#available-tools)的每個工具
> * **Purpose**：複雜研究、多步驟操作、程式碼修改
>
> 當任務需要探索和修改、複雜推理來解釋結果或多個相依步驟時，Claude 會委派給 general-purpose。

> [tab] Other
>
> Claude Code 包括用於特定任務的其他輔助代理。這些通常會自動呼叫，因此您不需要直接使用它們。
>
> | Agent | Model | Claude 何時使用它 |
> | :- | :- | :- |
> | claude | 沒有自己的；當 Claude 將其生成為 subagent 時遵循[模型順序](#choose-a-model) | 當任務不符合更專門的代理時。一個具有[可供 subagents 使用](#available-tools)的每個工具的全能代理。也是已分派[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md)的預設代理；[它啟動的權限模式](https://code.claude.com/docs/zh-TW/agent-view.md#permission-mode-model-and-effort)取決於工作階段的啟動方式 |
> | statusline-setup | Sonnet | 當您執行 `/statusline` 來配置您的狀態行時 |
> | claude-code-guide | Haiku | 當您提出有關 Claude Code 功能的問題時 |

內建 subagents 在互動式工作階段中預設會被註冊。若要限制它們：

* 若要封鎖特定的內建類型，請將其新增至 `permissions.deny`，如[停用特定 subagents](#disable-specific-subagents) 中所示。
* 若要防止 Claude 委派給任何 subagent，請使用 [`permissions.deny`](https://code.claude.com/docs/zh-TW/permissions#tool-specific-permission-rules) 拒絕 `Agent` 工具本身。
* 若要僅移除內建的 `Explore` 和 `Plan` subagents，請設定 [`CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS=1`](https://code.claude.com/docs/zh-TW/env-vars)。Claude 會直接讀取和探索檔案，而不是委派給它們。需要 Claude Code v2.1.198 或更新版本。
* 在[非互動式模式](https://code.claude.com/docs/zh-TW/headless.md)和 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 中，設定 [`CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1`](https://code.claude.com/docs/zh-TW/env-vars) 以移除所有內建類型，並僅提供您自己的。

當工作階段沒有 `general-purpose` subagent 可回退時，省略 `subagent_type` 的 Agent 工具呼叫會失敗，並出現 [`subagent_type is required`](https://code.claude.com/docs/zh-TW/errors#subagent-type-is-required) 錯誤。

除了這些內建 subagents 之外，您可以建立自己的 subagents，具有自訂提示、工具限制、權限模式、hooks 和 skills。以下部分展示如何開始和自訂 subagents。

## 快速入門：建立您的第一個 subagent

Subagents 是具有 YAML frontmatter 的 Markdown 檔案。若要建立一個，請要求 Claude 為您撰寫，或 [自行撰寫檔案](#write-subagent-files)。

本逐步指南建立一個使用者層級的 subagent，用於審查程式碼並提出改進建議。

**1. 要求 Claude 建立 subagent**

在 Claude Code 中，描述您想要的 subagent 及其儲存位置：

```text wrap theme={null}
Create a personal code-improver subagent in ~/.claude/agents/ that scans
files and suggests improvements for readability, performance, and best
practices. It should explain each issue, show the current code, and
provide an improved version. Make it read-only and have it use Sonnet.
```

Claude 會撰寫包含 `name`、`description`、`tools` 清單、`model` 和系統提示詞的檔案。

**2. 檢查檔案**

開啟 `~/.claude/agents/code-improver.md` 並確認 frontmatter 符合您的要求。結果如下所示：

```markdown theme={null}
---
name: code-improver
description: Scans files and suggests improvements for readability, performance, and best practices. Use after writing or modifying code.
tools: Read, Grep, Glob
model: sonnet
---

You are a code improvement specialist. For each issue you find, explain
the problem, show the current code, and provide an improved version.
```

因為檔案位於 `~/.claude/agents/`，所以 subagent 在您機器上的每個專案中都可用。若要改為將其範圍限制在一個專案，請將其移至該專案的 `.claude/agents/` 目錄。[選擇 subagent 範圍](#choose-the-subagent-scope) 比較了兩者。

**3. 試試看**

要求 Claude 委派給新的 subagent：

```text wrap theme={null}
Use the code-improver agent to suggest improvements in this project
```

Claude 委派給您的新 subagent，它掃描程式碼庫並返回改進建議。在逐字稿中，委派會顯示為工具呼叫列，顯示 subagent 的名稱，後面跟著簡短的工作描述，例如 `code-improver(Suggest code improvements)`。

如果 Claude 找不到新的 subagent，請重新啟動 Claude Code 並再試一次。這只在 `~/.claude/agents/` 在工作階段開始前不存在時發生，因為執行中的工作階段不會偵測到新建立的 `agents` 目錄。

現在您有一個 subagent，可以在機器上的任何專案中使用它來分析程式碼庫並提出改進建議。

您也可以手動撰寫 subagent 檔案、透過 CLI 旗標定義它們，或透過外掛分發它們。以下部分涵蓋所有設定選項。

> [!NOTE]
>
> 執行 `/agents` 會列印提醒，請您詢問 Claude 或直接編輯 `.claude/agents/` 和 `~/.claude/agents/`。
> 在 Claude Code v2.1.197 及更早版本上，`/agents` 開啟一個互動式精靈，其中包含列出即時 subagents 的 **Running** 標籤和用於建立、編輯和刪除它們的 **Library** 標籤。

## 設定子代理

子代理的檔案位置決定了誰可以使用它，其 frontmatter 決定了它可以做什麼。本節涵蓋子代理檔案的位置以及它們支援的每個欄位。

### 選擇子代理範圍

根據範圍將子代理檔案儲存在不同位置。當多個子代理共享相同名稱時，Claude Code 會使用來自優先順序較高位置的子代理。

| 位置 | 範圍 | 優先順序 | 如何建立 |
| :- | :- | :- | :- |
| 受管設定 | 組織範圍 | 1（最高） | 透過[受管設定](https://code.claude.com/docs/zh-TW/settings.md)部署 |
| `--agents` CLI 旗標 | 目前工作階段 | 2 | 啟動 Claude Code 時傳遞 JSON |
| `.claude/agents/` | 目前專案 | 3 | 詢問 Claude，或手動建立檔案 |
| `~/.claude/agents/` | 您的所有專案 | 4 | 詢問 Claude，或手動建立檔案 |
| Plugin 的 `agents/` 目錄 | 啟用 plugin 的位置 | 5（最低） | 與[plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)一起安裝 |

**專案子代理**（`.claude/agents/`）最適合特定於程式碼庫的子代理。將它們簽入版本控制，以便您的團隊可以協作使用和改進它們。

專案子代理是透過從目前工作目錄向上走來發現的，因此會掃描該處和儲存庫根目錄之間的每個 `.claude/agents/`。當這些巢狀目錄中的多個定義相同的 `name` 時，Claude Code 會使用最接近工作目錄的定義。

當您使用 `--add-dir` 或 `/add-dir` 新增目錄時，Claude Code 也會載入其 `.claude/agents/` 資料夾，以及您的專案子代理。請參閱[其他目錄](https://code.claude.com/docs/zh-TW/permissions.md#additional-directories-grant-file-access-not-configuration)以了解哪些其他設定類型從 `--add-dir` 載入。若要在不使用 `--add-dir` 的情況下跨專案共享子代理，請使用 `~/.claude/agents/` 或 [plugin](https://code.claude.com/docs/zh-TW/plugins/overview.md)。

**使用者子代理**（`~/.claude/agents/`）是在您的所有專案中可用的個人子代理。

Claude Code 會遞迴掃描 `.claude/agents/` 和 `~/.claude/agents/`，因此您可以將定義組織到子資料夾中，例如 `agents/review/` 或 `agents/research/`。子目錄路徑不會影響子代理的識別或叫用方式，因為身份僅來自 `name` frontmatter 欄位。

在整個樹中保持 `name` 值唯一：如果同一 `.claude/agents/` 目錄下（包括其子資料夾）的兩個檔案宣告相同的名稱，Claude Code 只會載入其中一個，由檔案系統讀取順序選擇，而不是依文件記載的優先順序。在巢狀專案目錄之間，則如上所述，最接近工作目錄的定義優先。[`/doctor`](https://code.claude.com/docs/zh-TW/commands#all-commands) 設定檢查會報告同一目錄中共享名稱的檔案，並建議重新命名或移除其餘檔案，只保留一個。

Plugin `agents/` 目錄也會遞迴掃描。與專案和使用者範圍不同，plugin 的 `agents/` 目錄內的子資料夾成為[範圍識別碼](#invoke-subagents-explicitly)的一部分：plugin `my-plugin` 中位於 `agents/review/security.md` 的檔案註冊為 `my-plugin:review:security`。

**CLI 定義的子代理**在啟動 Claude Code 時作為 JSON 傳遞。它們僅存在於該工作階段，不會儲存到磁碟，使其適合快速測試或自動化指令碼。您可以在單個 `--agents` 呼叫中定義多個子代理：

> [tab] macOS, Linux, WSL
>
> ```bash theme={null}
> claude --agents '{
>   "code-reviewer": {
>     "description": "Expert code reviewer. Use proactively after code changes.",
>     "prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
>     "tools": ["Read", "Grep", "Glob", "Bash"],
>     "model": "sonnet"
>   },
>   "debugger": {
>     "description": "Debugging specialist for errors and test failures.",
>     "prompt": "You are an expert debugger. Analyze errors, identify root causes, and provide fixes."
>   }
> }'
> ```

> [tab] Windows PowerShell
>
> ```powershell theme={null}
> claude --agents @'
> {
>   "code-reviewer": {
>     "description": "Expert code reviewer. Use proactively after code changes.",
>     "prompt": "You are a senior code reviewer. Focus on code quality, security, and best practices.",
>     "tools": ["Read", "Grep", "Glob", "Bash"],
>     "model": "sonnet"
>   },
>   "debugger": {
>     "description": "Debugging specialist for errors and test failures.",
>     "prompt": "You are an expert debugger. Analyze errors, identify root causes, and provide fixes."
>   }
> }
> '@
> ```

在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，`--agents` 也接受保存相同物件的 JSON 檔案的路徑，用於定義太大而無法在命令列上傳遞的情況。例如，`claude -p --agents ./agents.json "Review my changes"` 從該檔案讀取定義。在互動工作階段中，Claude Code 拒絕檔案路徑。檔案形式需要 Claude Code v2.1.281 或更新版本。

JSON 中的每個頂級鍵是代理的名稱，其值是該代理的定義。不要以 `-` 開頭的名稱。定義採用這些欄位：

* **`prompt`**：代理的系統提示，等同於檔案型子代理中的 markdown 主體。`prompt` 可能為空。如果您使用 `--agent` 選擇一個具有空 `prompt` 且沒有 `memory` 欄位的代理作為工作階段的代理，工作階段的系統提示保持不變。空 `prompt` 需要 Claude Code v2.1.281 或更新版本。
* **[Frontmatter 欄位](#supported-frontmatter-fields)**：`description`、`tools`、`disallowedTools`、`model`、`permissionMode`、`mcpServers`、`hooks`、`maxTurns`、`autoCompactWindow`、`skills`、`initialPrompt`、`memory`、`effort`、`background`、`omitClaudeMd` 和 `isolation`。
* **忽略的欄位**：`color` 和 `experimental` 在此不被接受，被忽略而不是拒絕。

有關 Claude Code 對無法載入的值所做的操作，以及跳過該檢查的旗標和環境變數，請參閱[`Invalid --agents configuration`](https://code.claude.com/docs/zh-TW/errors#invalid-agents-configuration)。

**受管子代理**由組織管理員部署。將 markdown 檔案放在[受管設定目錄](https://code.claude.com/docs/zh-TW/managed-settings.md#delivery-mechanisms)內的 `.claude/agents/` 中，使用與專案和使用者子代理相同的 frontmatter 格式。受管定義優先於具有相同名稱的專案和使用者子代理。

**Plugin 子代理**來自您已安裝的 [plugins](https://code.claude.com/docs/zh-TW/plugins/overview.md)。它們會自動與您的自訂子代理一起載入，並在 @-mention 預輸入中以其範圍名稱出現。有關建立 plugin 子代理的詳細資訊，請參閱 [plugin 元件參考](https://code.claude.com/docs/zh-TW/plugins/components.md#agents)。

> [!NOTE]
>
> 基於安全考量，外掛 subagent 不支援 `hooks`、`mcpServers` 或 `permissionMode` frontmatter 欄位。從外掛載入 agent 時，這些欄位會被忽略。如果您需要它們，請將 agent 檔案複製到 `.claude/agents/` 或 `~/.claude/agents/`。您也可以在 `settings.json` 或 `settings.local.json` 中將規則新增到 [`permissions.allow`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-allow)，但這些規則會套用於整個工作階段，而不僅是外掛 subagent。
>
> 如果您是該外掛的作者，請改為將 hook 放在外掛的 [`hooks/hooks.json`](https://code.claude.com/docs/zh-TW/plugins/components#hooks) 中，並將 MCP 伺服器放在其 [`.mcp.json`](https://code.claude.com/docs/zh-TW/plugins/components#mcp-servers) 中一併發布。只要外掛處於啟用狀態，它們就會套用，而不僅限於 subagent 內部。

您也可以將 subagent 定義重複用作 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 的隊員：在要求 Claude 產生隊員時指定 subagent 類型，Claude Code 就會將該定義的部分內容套用到該隊員。[將 subagent 定義用於隊員](https://code.claude.com/docs/zh-TW/agent-teams.md#use-subagent-definitions-for-teammates)說明了在各個顯示模式中會套用哪些範圍與哪些部分。

### 編寫子代理檔案

子代理檔案使用 YAML frontmatter 進行設定，後面是 Markdown 中的系統提示：

> [!NOTE]
>
> Claude Code 監視 `~/.claude/agents/` 和 `.claude/agents/`。當您在磁碟上新增或編輯子代理檔案，或要求 Claude 為您編寫一個時，Claude Code 會在幾秒內偵測到變更，下一次委派會使用更新的定義，無需重新啟動。
>
> 三種情況仍需要重新啟動：
>
> * 監視程式僅涵蓋工作階段開始時存在的目錄，因此在新 `agents` 目錄中建立範圍的第一個代理檔案後，重新啟動以載入它。
> * Claude Code 不監視透過 `--add-dir` 或 `/add-dir` 新增的目錄內的 `.claude/agents/`，因此在那裡新增或編輯子代理後，重新啟動以載入變更。
> * 使用 `--disable-slash-commands` 啟動的工作階段根本不監視這些目錄。

```markdown .claude/agents/code-reviewer.md theme={null}
---
name: code-reviewer
description: Reviews code for quality and best practices
tools: Read, Glob, Grep
model: sonnet
---

You are a code reviewer. When invoked, analyze the code and provide
specific, actionable feedback on quality, security, and best practices.
```

frontmatter 定義子代理的中繼資料和設定。主體成為指導子代理行為的系統提示。子代理僅接收此系統提示加上基本環境詳細資訊（如工作目錄），而不是 Claude Code 系統提示。

在[非互動模式](https://code.claude.com/docs/zh-TW/headless.md)中，傳遞 [`--append-subagent-system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags) 以將您的文字附加到每個子代理的系統提示末尾，包括巢狀子代理，除了[分叉子代理](#fork-the-current-conversation)，它重複使用對話自己的提示。需要 Claude Code v2.1.205 或更新版本。如果您的文字太長而無法在命令列上傳遞，請將其儲存到檔案並改為使用 `--append-subagent-system-prompt-file` 傳遞路徑。檔案旗標需要 Claude Code v2.1.261 或更新版本。

子代理在主對話的目前工作目錄中啟動。在子代理內，`cd` 命令不會在 Bash 或 PowerShell 工具呼叫之間持續，也不會影響主對話的工作目錄。若要改為給子代理儲存庫的隔離副本，請設定 [`isolation: worktree`](#supported-frontmatter-fields)。

具有 `isolation: worktree` 的 subagent 會在其 worktree 內執行其 Bash 和 PowerShell 命令。若命令的工作目錄改為解析到您的主簽出（例如因為 worktree 目錄在 subagent 執行期間被移除），該命令會失敗並出現錯誤。

此工作目錄檢查涵蓋包含您啟動 Claude Code 之目錄的整個儲存庫。當您的工作階段在其自己的連結 [worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 中執行時，檢查也會涵蓋該 worktree 所連結的主簽出。

對於 Bash 命令，Claude Code 也以兩種方式檢查命令本身：

* 它阻止將 git 重定向到主簽出的命令。
* 當它無法從命令文字驗證命令執行的任何 git 都保留在 worktree 內時，它拒絕命令，例如當命令名稱在執行時計算時。

重定向向量和形狀規則列在[Claude Code 如何強制隔離](https://code.claude.com/docs/zh-TW/worktrees.md#how-claude-code-enforces-isolation)下。PowerShell 命令僅獲得工作目錄檢查。

[Monitor](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool) 命令經過與 Bash 命令相同的工作目錄和命令內容檢查。

當主對話本身在 worktree 中隔離執行時，Claude Code 對工作階段和它生成的每個子代理應用相同的檢查，包括沒有 `isolation: worktree` 的子代理；請參閱[Claude Code 如何強制隔離](https://code.claude.com/docs/zh-TW/worktrees.md#how-claude-code-enforces-isolation)。

### Frontmatter 參考

使用 YAML [frontmatter](https://code.claude.com/docs/zh-TW/glossary.md#frontmatter) 在檔案頂部的 `---` 標記之間設定子代理，並在結束 `---` 之後將其系統提示寫為 Markdown。只有 `name` 和 `description` 是必需的。

多字欄位名稱使用 camelCase，例如 `maxTurns` 和 `disallowedTools`，必須與表格完全相符：Claude Code 會忽略它無法識別的欄位而不報告錯誤。

* 若要找出已載入之 subagent 中拼錯的欄位，請在 shell 中執行 [`claude --debug`](https://code.claude.com/docs/zh-TW/cli-reference#cli-flags)，並在位於 `~/.claude/debug/<session-id>.txt` 的除錯日誌中搜尋 `does not recognize or apply`。除錯日誌會列出 subagent 檔案中最多五個 Claude Code 無法識別的頂層欄位，並在有相近的支援欄位時提供可能想要的名稱。需要 Claude Code v2.1.296 或更新版本。
* 若要找出 subagent 檔案未載入的原因，請參閱[Claude Code 跳過的 subagent 檔案](#subagent-files-claude-code-skips)。

| 欄位 | 必需 | 描述 |
| :- | :- | :- |
| `name` | 是 | 最多 256 個字元的唯一識別碼，例如 `code-reviewer` 或 `reviewer-v2`。[Hook](https://code.claude.com/docs/zh-TW/hooks.md#subagentstart) 會以 `agent_type` 接收此值。檔案名稱不必相符。名稱不能包含 `:`，它保留給[外掛範圍識別碼](https://code.claude.com/docs/zh-TW/plugins/overview.md)使用，例如 `my-plugin:reviewer` |
| `description` | 是 | Claude 應何時委派給此子代理 |
| `tools` | 否 | 子代理可以使用的[工具](#available-tools)，作為逗號分隔的字串，例如 `Read, Grep, Bash` 或 YAML 列表。如果省略，繼承子代理可用的每個工具。如果列表中沒有條目解析為工具，子代理通常[無法啟動](https://code.claude.com/docs/zh-TW/errors.md#agent-would-be-spawned-with-zero-tools)並出現錯誤，命名未解析的條目。若要將 Skills 預載入上下文，請使用 `skills` 欄位而不是在此列出 `Skill` |
| `disallowedTools` | 否 | 要拒絕的工具，會從繼承或指定的清單中移除。格式與 `tools` 相同。具有指定符的條目（例如 `Bash(git push *)`）仍會[移除整個工具](#restrict-which-tools-a-subagent-can-use) |
| `model` | 否 | 要使用的[模型](#choose-a-model)：`sonnet`、`opus`、`haiku`、`fable`、完整模型 ID（例如 `claude-opus-5-5`）或 `inherit`。當您省略它時，Claude Code 會在[子代理模型順序](#choose-a-model)中選擇模型 |
| `permissionMode` | 否 | [權限模式](#permission-modes)：`default`、`acceptEdits`、`auto`、`dontAsk`、`bypassPermissions`、`plan`，或作為 `default` 別名的 `manual`。對[外掛 subagent](#choose-the-subagent-scope) 會被忽略 |
| `maxTurns` | 否 | 子代理停止前的最大代理轉數。當子代理達到限制時，Claude Code 返回其輸出標記為部分，Claude 可以[恢復它](#resume-subagents)以繼續。部分標記需要 Claude Code v2.1.246 或更新版本 |
| `autoCompactWindow` | 否 | 將此 subagent 的[自動壓縮視窗](#subagent-auto-compact-window)降低至 `100000` 到 `1000000` 之間的 token 數。需要 Claude Code v2.1.296 或更新版本 |
| `skills` | 否 | 在啟動時預載入子代理上下文的[技能](https://code.claude.com/docs/zh-TW/skills.md)。注入完整技能內容，而不僅僅是描述。子代理仍然可以透過 Skill 工具叫用未列出的專案、使用者和 plugin 技能 |
| `mcpServers` | 否 | 此子代理可用的 [MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md)。每個條目要麼是參考已設定伺服器的伺服器名稱（例如 `"slack"`），要麼是內聯定義，伺服器名稱作為鍵，完整 [MCP 伺服器設定](https://code.claude.com/docs/zh-TW/mcp.md#installing-mcp-servers)作為值。對於 [plugin 子代理](#choose-the-subagent-scope)被忽略 |
| `hooks` | 否 | [生命週期 hooks](#define-hooks-for-subagents) 範圍限於此子代理。對於 [plugin 子代理](#choose-the-subagent-scope)被忽略 |
| `memory` | 否 | [持久記憶範圍](#enable-persistent-memory)：`user`、`project` 或 `local`。啟用跨工作階段學習 |
| `background` | 否 | 設為 `true` 可讓此 subagent 即使在 Claude 要求等待它時仍保持在背景中。預設情況下，Claude 從主對話產生的 subagent 本來就會[在背景中啟動](#run-subagents-in-foreground-or-background) |
| `omitClaudeMd` | 否 | 設為 `true` 可讓此 subagent 啟動時，其[初始上下文](#what-loads-at-startup)中不含使用者、專案和本機 CLAUDE.md 檔案；[受管原則檔案](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load)仍會載入，但[受管 subagent](#choose-the-subagent-scope) 除外。適用於從委派提示詞取得所需一切的 subagent。當 agent 透過 `--agent` 或 `agent` 設定作為主工作階段 agent 執行時會被忽略。需要 Claude Code v2.1.271 或更新版本 |
| `effort` | 否 | 此 subagent 執行時的 effort 等級。會覆寫工作階段的 effort 等級，但不會覆寫 [`CLAUDE_CODE_EFFORT_LEVEL`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數。選項：`low`、`medium`、`high`、`xhigh`、`max`；可用等級取決於模型。請參閱[選擇 effort 等級](#choose-an-effort-level) |
| `isolation` | 否 | 設定為 `worktree` 以在臨時 [git worktree](https://code.claude.com/docs/zh-TW/worktrees.md) 中執行子代理，給它儲存庫的隔離副本，預設從您的[預設分支](https://code.claude.com/docs/zh-TW/worktrees.md#choose-the-base-branch)分支，而不是父工作階段的 `HEAD`。如果子代理不進行任何變更，worktree 會自動清理 |
| `color` | 否 | 子代理在任務列表和文字記錄中的顯示顏色。接受 `red`、`blue`、`green`、`yellow`、`purple`、`orange`、`pink` 或 `cyan` |
| `initialPrompt` | 否 | 當此代理作為主工作階段代理執行時（透過 `--agent` 或 `agent` 設定），自動提交為第一個使用者轉。[命令](https://code.claude.com/docs/zh-TW/commands.md)和[技能](https://code.claude.com/docs/zh-TW/skills.md)被處理。前置任何使用者提供的提示。對於 [plugin 子代理](#choose-the-subagent-scope)被忽略 |
| `experimental` | 否 | 實驗選項的對應。將其 `cacheTtl` 鍵設定為 `5m` 或 `1h` 以選擇此子代理請求的[提示快取生命週期](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)。此值套用於 frontmatter 在[快取生命週期優先順序](https://code.claude.com/docs/zh-TW/prompt-caching.md#choose-the-ttl-yourself)中所處的位置。Claude Code 忽略任何其他值，在您的 Claude 訂閱使用使用額度時忽略 `1h`，並僅從子代理檔案讀取欄位。需要 Claude Code v2.1.248 或更新版本 |

在 `experimental` 對應內寫入 `cacheTtl`，而不是在 frontmatter 的頂級。

```yaml theme={null}
---
name: repo-auditor
description: Audits a large repository and reports what it finds
experimental:
  cacheTtl: 1h
---
```

#### Claude Code 跳過的子代理檔案

Claude Code 在專案、使用者或受管 `agents` 目錄中跳過檔案，或在您使用 `--add-dir` 新增的目錄下的檔案，而不在工作階段中報告它，當 frontmatter 有以下任何問題時：

* **沒有 `name`**：Claude Code 將檔案視為保存在代理旁邊的文件。
* **不是檔案第一行的開啟 `---`**：Claude Code 讀取檔案為沒有 frontmatter，並將其視為文件。
* **`name` 以 `-` 開頭、包含 `:`，或超過 256 個字元**：Claude Code 會略過該檔案，並將錯誤寫入除錯日誌。
* **有 `name` 但沒有 `description`**：Claude Code 跳過檔案並將原因寫入偵錯日誌。
* **不解析的 YAML**：Claude Code 不從檔案讀取任何欄位，跳過它，並將解析錯誤寫入偵錯日誌。

若要查看偵錯日誌，請使用 `--debug` 執行 Claude Code。

[plugin 子代理](https://code.claude.com/docs/zh-TW/plugins/components.md#agents)的 frontmatter 沒有 `name` 或不解析仍然載入，在其檔案名稱下。

##### 在工作階段前檢查 `agents` 目錄

若要找出 `agents` 目錄中 frontmatter 不解析的檔案，請針對目錄執行 `claude plugin validate`，例如 `.claude/agents` 或 `~/.claude/agents`。Claude Code 僅檢查[您命名的目錄](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#validate-a-directory)，不標記 frontmatter 解析但沒有 `name` 的檔案。需要 Claude Code v2.1.233 或更新版本。

### 選擇模型

`model` 欄位控制子代理使用的模型：

* **模型別名**：使用可用別名之一：`sonnet`、`opus`、`haiku` 或 `fable`
* **完整模型 ID**：使用完整模型 ID，例如 `claude-opus-5-5` 或 `claude-sonnet-5`。接受與 `--model` 旗標相同的值
* **inherit**：使用與主對話相同的模型

當 Claude 叫用 subagent 時，它也可以為該次叫用傳遞 `model` 參數。在 Agent 工具呼叫中，該參數接受模型別名：`sonnet`、`opus`、`haiku` 或 `fable`。Claude 無法在該呼叫中傳遞完整模型 ID 或 `inherit`。Claude Code 會依此順序解析 subagent 的模型：

1. 每次叫用 `model` 參數
2. 子代理定義的 `model` frontmatter，其中 `inherit` 選擇主對話的模型
3. [`CLAUDE_CODE_SUBAGENT_MODEL`](https://code.claude.com/docs/zh-TW/model-config#environment-variables) 環境變數，當您將其設定為模型別名或模型 ID 時
4. 主對話的模型

如果已安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 在其 [`agent.spawn`](https://code.claude.com/docs/zh-TW/plugins/mods/reference#subagents) hook 中設定了模型，Claude Code 會以該模型取代每次叫用的參數。

在兩種情況下，每次叫用參數或 frontmatter 中的家族別名（例如 `opus`）解析為主對話的模型，而不是[別名指向的版本](https://code.claude.com/docs/zh-TW/model-config.md#model-aliases)：

* **主對話的模型屬於該家族**：子代理在主對話的確切模型上執行，包括任何 `[1m]` 尾碼，因此它獲得與主對話相同的[擴展上下文](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)視窗。
* **Claude Code 無法判斷主對話的模型家族，在[Anthropic API 以外的提供者](https://code.claude.com/docs/zh-TW/third-party-integrations.md)上**：這可能發生在 Amazon Bedrock 上的[應用程式推論設定檔 ARN](https://code.claude.com/docs/zh-TW/amazon-bedrock.md#iam-configuration)，Claude Code 尚未解析為支援模型。此情況僅涵蓋 `opus` 別名，當您設定 [`ANTHROPIC_DEFAULT_OPUS_MODEL`](https://code.claude.com/docs/zh-TW/model-config#environment-variables) 時不適用，因為 `opus` 然後解析為您設定的模型。

`CLAUDE_CODE_SUBAGENT_MODEL` 中的別名一律解析為別名指向的版本，即使它指定的是主對話的家族。將此變數設定為 `inherit` 等同於不設定它。

單獨設定 `CLAUDE_CODE_SUBAGENT_MODEL` 不會改變內建 Explore 和 Plan 子代理執行的模型。若要改變它，請參閱[在一個模型上執行每個子代理](#run-every-subagent-on-one-model)。

在 v2.1.251 之前，`CLAUDE_CODE_SUBAGENT_MODEL` 在此順序中排在第一位，並覆蓋每次叫用參數和 frontmatter，包括 `model: inherit`。

Claude Code 根據您組織的 [`availableModels`](https://code.claude.com/docs/zh-TW/model-config#restrict-model-selection) 允許清單檢查每次叫用參數、frontmatter 和環境變數值。對於被阻止的值，它替換另一個模型：

* 當被阻止的值是家族別名（例如 `opus`）時，Claude Code 在允許清單允許的該家族的最新版本上執行子代理，遵循與 `/model` 相同的[替換規則和提供者範圍](https://code.claude.com/docs/zh-TW/model-config.md#restrict-model-selection)。在 v2.1.222 之前，Claude Code 也在被阻止的家族別名的繼承模型上執行子代理。
* 對於任何其他被阻止的值，在該替換不操作的提供者上，或當允許清單允許該家族的沒有版本時，Claude Code 改為在繼承模型上執行子代理。如果您設定 `CLAUDE_CODE_SUBAGENT_MODEL`，Claude Code 首先嘗試該模型，在這些相同的規則下。

在互動工作階段中，Claude Code 顯示警告，命名請求的模型和子代理執行的模型，用於任一替換。

若要檢查 subagent 正在執行的模型，請執行 [`/tasks`](https://code.claude.com/docs/zh-TW/commands)。Claude Code 會在 subagent 的列上列出模型，並在有為該 subagent 設定 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)時一併顯示。需要 Claude Code v2.1.242 或更新版本。

每次叫用的 `model` 參數也適用於 subagent [被繼續或收到後續訊息](#resume-subagents)時，因此 subagent 會保持在該模型上。

從 v2.1.198 開始，子代理也繼承主對話的[擴展思考](https://code.claude.com/docs/zh-TW/model-config.md#extended-thinking)設定：如果思考在您的工作階段中開啟，它對子代理開啟，如果關閉，它保持關閉。沒有每個子代理思考設定。在 v2.1.198 之前，子代理執行時禁用擴展思考，無論主對話的設定如何。

#### 在一個模型上執行每個子代理

`CLAUDE_CODE_SUBAGENT_MODEL` 是預設值，因此子代理的定義或 Claude 傳遞的模型仍然優先於它。若要將一個模型應用於每個子代理、[隊友](https://code.claude.com/docs/zh-TW/agent-teams.md#specify-teammates-and-models) 和[工作流代理](https://code.claude.com/docs/zh-TW/workflows.md)，也設定 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` 為 `1`。需要 Claude Code v2.1.257 或更新版本。

* 如果您設定兩個變數，子代理在 `CLAUDE_CODE_SUBAGENT_MODEL` 中的模型上執行。
* 如果您只設定 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`，subagent 會在主對話的模型上執行，但內建的 Explore subagent 例外，它會在[內建 subagent 中為其列出的模型](#built-in-subagents)上執行。

例如，若要在 Haiku 上執行每個子代理，在[設定檔](https://code.claude.com/docs/zh-TW/settings.md)的 `env` 區塊中設定兩個變數：

```json theme={null}
{
  "env": {
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku",
    "CLAUDE_CODE_SUBAGENT_MODEL_FORCE": "1"
  }
}
```

若要檢查設定是否生效，在子代理執行時執行 [`/tasks`](https://code.claude.com/docs/zh-TW/commands)。子代理的列顯示它執行的模型。

當 `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` [開啟](https://code.claude.com/docs/zh-TW/env-vars.md)時，Claude Code 會忽略 subagent 定義中的 `model` 欄位，且 Claude 在啟動 subagent 時無法傳遞模型。以下 subagent 仍會在主對話的模型上執行：

* [分叉](#fork-the-current-conversation)
* [在子代理中執行的技能](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent)，具有 `model: inherit`

### 選擇 effort 等級

若要讓 subagent 以其自己的 [effort 等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)執行，請在其定義中設定 [`effort`](#supported-frontmatter-fields) 欄位。

當您要求 Claude 以特定 effort 等級執行非分叉 subagent 時，它也可以為該次叫用傳遞 `effort` 參數。此參數會覆寫 `effort` 欄位，並在 subagent [被恢復](#resume-subagents)時持續生效。[`CLAUDE_CODE_EFFORT_LEVEL`](https://code.claude.com/docs/zh-TW/env-vars#variables) 環境變數優先於兩者。每次叫用的參數需要 Claude Code v2.1.292 或更新版本。

#### 當 subagent 沒有 `effort` 欄位或參數時

在主對話的模型上，subagent 會以您在工作階段中選擇的等級執行，例如透過 `/effort` 選擇，或以 `--effort` 設定。在其他模型上，[該等級不適用](https://code.claude.com/docs/zh-TW/model-config.md#effort-level-of-subagents-and-teammates)。若要選擇其等級，請設定 `effort` 欄位。

### 控制子代理功能

您可以透過工具存取、權限模式和條件規則控制子代理可以做什麼。

#### 可用工具

子代理繼承[內建工具](https://code.claude.com/docs/zh-TW/tools-reference.md)和主對話中可用的 MCP 工具，由兩個篩選器縮小：第一個從每個子代理移除工具的簡短列表，第二個減少在[背景中](#run-subagents-in-foreground-or-background)執行的子代理的內建工具集，這是預設值。在 macOS、Linux 和 WSL 上，當主對話沒有時，子代理也可以接收 Glob 和 Grep 工具，如[Glob 工具行為](https://code.claude.com/docs/zh-TW/tools-reference.md#glob-tool-behavior)下所述。[分叉](#fork-the-current-conversation)跳過兩個篩選器並接收主對話的確切工具池。第一個篩選器移除這些工具，即使在 `tools` 欄位中列出：

* `Agent`，當子代理在[深度限制](#let-subagents-spawn-their-own-subagents)時；在[分叉](#fork-the-current-conversation)中工具保持列出但返回錯誤而不是生成
* `AskUserQuestion`
* `EndConversation`，只能結束主對話；請參閱[EndConversation 工具行為](https://code.claude.com/docs/zh-TW/tools-reference.md#endconversation-tool-behavior)
* `EnterPlanMode`
* `ExitPlanMode`，除非子代理的 [`permissionMode`](#permission-modes) 是 `plan`
* `ScheduleWakeup`
* `WaitForMcpServers`
* `Workflow`

第二個篩選器適用於在背景中執行的子代理。`Agent` 和 `ExitPlanMode` 無論子代理在哪裡執行都遵循第一個篩選器的條件。除這兩個工具外，背景子代理保留每個 MCP 工具，但內建工具只保留這些：`Read`、`Grep`、`Glob`、`LSP`、`Bash`、`PowerShell`、`Edit`、`Write`、`NotebookEdit`、`WebFetch`、`WebSearch`、`TodoWrite`、`Skill`、`ToolSearch`、`EnterWorktree`、`ExitWorktree`、`Monitor`、`TaskStop`、`SendMessage` 和 `Artifact`，加上[`SubagentHandback`](https://code.claude.com/docs/zh-TW/tools-reference)用於透過它報告的子代理。Claude Code 從背景子代理移除每個其他內建工具，無論繼承或在 `tools` 欄位中列出，因此相同定義可以在前景和背景中解析為不同的工具。移除不會報告錯誤，除非它使 `tools` 列表[解析為無](https://code.claude.com/docs/zh-TW/errors.md#agent-would-be-spawned-with-zero-tools)。

在 v2.1.280 之前，背景子代理無法使用 `LSP`。

[`ListAgents`](https://code.claude.com/docs/zh-TW/cross-session-messaging)遵循這些篩選器，如任何內建工具：前景子代理在啟用跨工作階段訊息的工作階段中繼承它，背景子代理不保持它。

[agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 中的隊員另外會保留任務工具和 cron 工具：`TaskCreate`、`TaskGet`、`TaskList`、`TaskUpdate`、`CronCreate`、`CronDelete` 和 `CronList`。在[沒有 Task 工具的工作階段](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)中，Claude Code 也不會向 subagent 提供任務工具，即使 subagent 執行的是不同的模型。行程內隊員也以相同方式遵循您的工作階段。若要了解分割窗格隊員是否具有任務工具，請參閱 [Task 工具可用性](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)。

#### 限制 subagent 可以使用的工具

若要限制工具，請使用 `tools` 欄位作為允許清單，或使用 `disallowedTools` 欄位作為拒絕清單。如果兩者都設定，會先套用 `disallowedTools`，然後針對剩餘的工具池解析 `tools`。在兩者中都列出的工具會被移除。

此範例使用 `tools` 僅允許 Read、Grep、Glob 和 Bash。subagent 無法編輯檔案、寫入檔案或使用任何 MCP 工具：

```yaml theme={null}
---
name: safe-researcher
description: Research agent with restricted capabilities
tools: Read, Grep, Glob, Bash
---
```

此範例使用 `disallowedTools` 繼承子代理的工具池，除了 Write 和 Edit。子代理保持 Bash、MCP 工具和其池的其餘部分：

```yaml theme={null}
---
name: no-writes
description: Inherits the available tools except file writes
disallowedTools: Write, Edit
---
```

當 `tools` 清單中沒有任何項目解析為工具時，例如因為每個項目都拼錯，或指定的是 subagent 無法使用的工具，Claude Code 通常會拒絕啟動 subagent，且 Agent 工具會傳回列出未解析項目的錯誤；請參閱 [Agent would be spawned with zero tools](https://code.claude.com/docs/zh-TW/errors.md#agent-would-be-spawned-with-zero-tools) 以了解該訊息以及如何修正每個項目。

`tools` 和 `disallowedTools` 欄位也接受代表整個 MCP 伺服器的條目：

| 目標 | 欄位 | 範例條目 |
| :- | :- | :- |
| 讓 subagent 取得某個伺服器的每個工具 | `tools` | `mcp__github__*` |
| 不提供某個伺服器的工具 | `disallowedTools` | `mcp__github` 或 `mcp__github__*` |
| 不提供任何伺服器的每個 MCP 工具 | `disallowedTools` | `mcp__*` |

此範例會移除 `github` MCP 伺服器的每個工具，同時在 subagent 的工具池中保留其他伺服器的工具和內建工具：

```yaml theme={null}
---
name: local-only
description: Inherits every tool except those from the github MCP server
disallowedTools: mcp__github
---
```

具有指定符的 `disallowedTools` 條目（例如 `Bash(git push *)`）仍然從子代理移除整個工具，而不僅僅是匹配的命令。若要保持 Bash 並阻止特定命令，在您的設定中新增[Bash 拒絕規則](https://code.claude.com/docs/zh-TW/permissions.md#bash)，例如 `Bash(git push *)` 到 `permissions.deny`。規則適用於主對話和子代理。

##### 包含雙底線的 MCP 伺服器名稱

如果 subagent 無法取得名稱包含 `__` 之 MCP 伺服器（例如 `reports__v2`）的任何工具，請檢查 subagent 的 `mcp__` 項目：

* **在 `tools` 中**：寫入 `mcp__`，後接[伺服器的完整名稱](https://code.claude.com/docs/zh-TW/permissions.md#mcp)和 `__*`，例如 `mcp__reports__v2__*`。若沒有結尾的 `__*`，`mcp__reports__v2` 不會符合該伺服器的任何工具。
* **在 `disallowedTools` 中**：尋找 `mcp__reports` 或 `mcp__reports__*`，這兩個項目會排除名為 `reports` 的伺服器。使用其中任一項目時，subagent 也會失去每個 `reports__v2` 工具，因為這些工具名稱同樣以 `mcp__reports__` 開頭。若只要排除 `reports` 伺服器的工具，請改為逐一列出它們，例如 `mcp__reports__run_query`。

#### 限制可以生成的子代理

當代理使用 `claude --agent` 作為主執行緒執行時，它可以使用 Agent 工具生成子代理。若要限制它可以生成的子代理類型，在 `tools` 欄位中使用 `Agent(agent_type)` 語法。

> [!NOTE]
>
> 在版本 2.1.63 中，Task 工具被重新命名為 Agent。設定和代理定義中的現有 `Task(...)` 參考仍然作為別名工作。

```yaml theme={null}
---
name: coordinator
description: Coordinates work across specialized agents
tools: Agent(worker, researcher), Read, Bash
---
```

這是允許清單：只有 `worker` 和 `researcher` 子代理可以生成。如果代理嘗試生成任何其他類型，請求失敗，代理僅看到其提示中允許的類型。若要在允許所有其他類型時阻止特定代理，改為使用 [`permissions.deny`](#disable-specific-subagents)。

若要允許生成任何子代理而不受限制，使用 `Agent` 不帶括號：

```yaml theme={null}
tools: Agent, Read, Bash
```

如果您完全從 `tools` 列表中省略 `Agent`，代理無法使用 Agent 工具生成任何子代理。

`Agent(agent_type)` 允許清單語法僅適用於使用 `claude --agent` 作為主執行緒執行的代理。在子代理定義中，在 `tools` 中列出 `Agent` 讓該子代理在[深度限制](#let-subagents-spawn-their-own-subagents)允許時生成自己的子代理，但括號內的任何類型列表被忽略。

#### 將 MCP 伺服器範圍限於子代理

使用 `mcpServers` 欄位給子代理存取在主對話中不可用的 [MCP](https://code.claude.com/docs/zh-TW/mcp.md) 伺服器。此處定義的內聯伺服器在子代理啟動時連接，受[代理檔案資料夾的信任規則](#inline-server-trust)約束，並在完成時斷開連接。字串參考共享父工作階段的連接。

> [!NOTE]
>
> `mcpServers` 欄位適用於代理檔案可以執行的兩個上下文：
>
> * 作為子代理，透過 Agent 工具或 @-mention 生成
> * 作為主工作階段，使用 [`--agent`](#invoke-subagents-explicitly) 或 `agent` 設定啟動
>
> 當代理是主工作階段時，內聯伺服器定義在啟動時連接，與來自 [`.mcp.json`](https://code.claude.com/docs/zh-TW/mcp) 和設定檔的伺服器一起，在[代理檔案資料夾的信任規則](#inline-server-trust)下。在 `/mcp` 中，您之前使用過的遠端（HTTP 或 SSE）伺服器可以顯示[`cached` 狀態](https://code.claude.com/docs/zh-TW/mcp#managing-your-servers)；Claude Code 在 Claude 首次呼叫其工具之一時連接它。

列表中的每個條目要麼是內聯伺服器定義，要麼是參考工作階段中已設定的 MCP 伺服器的字串：

```yaml theme={null}
---
name: browser-tester
description: Tests features in a real browser using Playwright
mcpServers:
  # Inline definition: scoped to this subagent only
  - playwright:
      type: stdio
      command: npx
      args: ["-y", "@playwright/mcp@latest"]
  # Reference by name: reuses an already-configured server
  - github
---

Use the Playwright tools to navigate, screenshot, and interact with pages.
```

內聯定義使用與 `.mcp.json` 伺服器條目相同的架構，以伺服器名稱為鍵，並支援 `stdio`、`http`、`sse` 和 `ws` 類型。

若要將 MCP 伺服器完全保留在主對話之外，並避免其工具描述在那裡消耗上下文，在此處內聯定義它，而不是在 `.mcp.json` 中。子代理獲得工具；父對話不。

適用於主工作階段的 MCP 限制，也涵蓋在 subagent frontmatter 中宣告的伺服器：

* [`--strict-mcp-config`](https://code.claude.com/docs/zh-TW/cli-reference) 和 [`--bare`](https://code.claude.com/docs/zh-TW/cli-reference)
* [企業受管 MCP 設定](https://code.claude.com/docs/zh-TW/managed-mcp.md)
* [`allowedMcpServers` 和 `deniedMcpServers` 原則](https://code.claude.com/docs/zh-TW/managed-mcp#policy-based-control-with-allowlists-and-denylists)

當其中任一項封鎖某個伺服器時，Claude Code 會略過它，並顯示列出被封鎖伺服器的警告。

受管設定的限制適用於每個 subagent，無論其定義方式為何。`--strict-mcp-config` 不會篩選您透過 `--agents` 或 SDK `agents` 選項以內嵌方式傳遞的伺服器，因為這些屬於呼叫者的明確輸入。

#### 內嵌 MCP 伺服器所需的信任

對於您專案的 `.claude/agents/` 目錄中，或 `--add-dir` 目錄之 `.claude/agents/` 中的 agent 檔案，Claude Code 只有在您[信任該 agent 檔案所在的資料夾](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)之後，才會載入其中的[內嵌 MCP 伺服器](#scope-mcp-servers-to-a-subagent)。在 v2.1.238 之前，Claude Code 載入這些伺服器時不會檢查信任。

* **不計算的信任**：父資料夾的信任，以及 `-p` 或 SDK 工作階段為[設定檔中的 hooks](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)獲得的自動信任
* **直到那時**：Claude Code 跳過該代理檔案中的每個內聯伺服器，並將 `~/.claude.json` 的確切 `projects["<path>"].hasTrustDialogAccepted` 鍵寫入偵錯日誌
* **`--add-dir` 目錄**：您受信任工作區儲存庫外的目錄需要自己的信任條目，因為其 `.claude/agents/` 檔案不繼承您工作區的信任

Claude Code 載入兩種伺服器而不檢查代理檔案來自的資料夾的信任：

* 參考您已設定的伺服器的名稱
* 來自 `~/.claude/agents/` 中代理檔案的內聯伺服器，在您使用 `--agents` 或 SDK `agents` 選項傳遞的檔案中，或受管設定提供的檔案中

#### 權限模式

設定 `permissionMode` 以選擇子代理執行的權限模式。使用模式的設定值，因此手動模式是 `default`。如果您不設定它，子代理繼承主對話的[權限模式](https://code.claude.com/docs/zh-TW/permission-modes.md)。

主對話的權限模式決定 Claude Code 是否使用您設定的值：

* 當主對話在 `bypassPermissions`、`acceptEdits` 或[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)中時，子代理在該相同模式中執行，Claude Code 忽略您設定的 `permissionMode`。在自動模式下，分類器使用主對話的阻止和允許規則評估子代理的工具呼叫。當子代理完成時，分類器也在報告被傳遞之前檢查其工作和最終報告，如[自動模式如何處理子代理](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)所述。
* 當主對話處於 `plan` 模式時，無論您設定哪個 `permissionMode`，subagent 都會保持在 plan mode，除非它在 [agent teams 規則](https://code.claude.com/docs/zh-TW/agent-teams.md#have-teammates-plan-before-implementing)下作為 [agent team 隊員](#subagent-names)執行。如果您設定了 `dontAsk`，subagent 也不會提示您：plan mode 原本會要求您核准的動作會改為被拒絕。
* 當主對話處於 `default` 或 `dontAsk` 模式時，subagent 會以您設定的權限模式執行。在以下情況下，它會改為保持主對話的權限模式：
  * 您設定了 `bypassPermissions`。`bypassPermissions` 例外需要 Claude Code v2.1.267 或更新版本。
  * 您設定了 `auto`，但 subagent [無法使用自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)，例如設定檔設定了 [`disableAutoMode`](https://code.claude.com/docs/zh-TW/settings-reference#disableautomode)，或 subagent 的模型不支援自動模式。

`permissionMode` 接受這些值，以及 `manual` 作為 `default` 的別名：

| 模式 | 行為 |
| :- | :- |
| `default` | 手動模式：提示權限 |
| `acceptEdits` | 自動接受檔案編輯和工作目錄或 `additionalDirectories` 中路徑的常見檔案系統命令 |
| `auto` | [自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)：背景分類器檢查命令和受保護目錄寫入 |
| `dontAsk` | 自動拒絕會觸發提示的呼叫，但您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准[其中部分呼叫](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。明確允許的工具仍可使用。`AskUserQuestion`、標記為 [`requiresUserInteraction`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具、[從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)，以及在該設定到達 Claude Code 的工作階段中[您的組織設定為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具，即使您已允許也會被拒絕 |
| `bypassPermissions` | [跳過權限提示](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)。子代理僅在主對話執行此模式時在此模式中執行 |
| `plan` | Plan 模式（唯讀探索） |

#### 將技能預載入子代理

使用 `skills` 欄位在啟動時將技能內容注入子代理的上下文。這給子代理領域知識，而不需要它在執行期間發現和載入技能。

```yaml theme={null}
---
name: api-developer
description: Implement API endpoints following team conventions
skills:
  - api-conventions
  - error-handling-patterns
---

Implement API endpoints. Follow the conventions and patterns from the preloaded skills.
```

每個列出之 skill 的完整內容會在啟動時注入 subagent 的上下文，最多為清單中前 32 個不重複的名稱。此欄位控制哪些 skill 會被預先載入，而不是 subagent 可以存取哪些 skill：沒有它，subagent 仍可在執行期間透過 Skill 工具探索並叫用專案、使用者和外掛 skill。若要完全禁止 subagent 叫用 skill，請從 [`tools`](#available-tools) 清單中省略 `Skill`，或將其新增到 `disallowedTools`。

您無法預先載入設定了 [`disable-model-invocation: true`](https://code.claude.com/docs/zh-TW/skills#control-who-invokes-a-skill) 的 skill，因為預先載入取自 Claude 可叫用的同一組 skill。這包括內建的 `/verify` skill，Claude 無法自行執行它。

如果列出的技能遺失或被禁用，例如由您組織的原則，Claude Code 跳過它並將警告記錄到偵錯日誌。

> [!NOTE]
>
> 這與[在子代理中執行技能](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent)相反。在子代理中使用 `skills` 時，子代理控制系統提示並載入技能內容。在技能中使用 `context: fork` 時，技能內容被注入您指定的代理。在兩種情況下，子代理啟動時沒有您的對話歷史。

#### 啟用持久記憶

`memory` 欄位給子代理一個在對話中存活的持久目錄。子代理使用此目錄隨著時間建立知識，例如程式碼庫模式、偵錯見解和架構決策。

```yaml theme={null}
---
name: code-reviewer
description: Reviews code for quality and best practices
memory: user
---

You are a code reviewer. As you review code, update your agent memory with
patterns, conventions, and recurring issues you discover.
```

根據記憶應該應用的廣泛程度選擇範圍：

| 範圍 | 位置 | 使用時機 |
| :- | :- | :- |
| `user` | `~/.claude/agent-memory/<name-of-agent>/` | 子代理應該記住跨所有專案的學習 |
| `project` | `.claude/agent-memory/<name-of-agent>/` | 子代理的知識是專案特定的並可透過版本控制共享 |
| `local` | `.claude/agent-memory-local/<name-of-agent>/` | 子代理的知識是專案特定的但不應簽入版本控制 |

子代理記憶是[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory)的一部分：如果您關閉自動記憶，使用 `autoMemoryEnabled` 設定或 `CLAUDE_CODE_DISABLE_AUTO_MEMORY`，`memory` 欄位無效，子代理啟動時沒有記憶指示或下面描述的記憶工具存取。

當記憶啟用時：

* 子代理的系統提示包括讀取和寫入記憶目錄的指示。
* 子代理的系統提示也包括記憶目錄中 `MEMORY.md` 的前 200 行或 25KB（以先到者為準），以及如果超過該限制則策劃 `MEMORY.md` 的指示。
* Read、Write 和 Edit 工具自動啟用，以便子代理可以管理其記憶檔案。

##### 持久記憶提示

* `project` 是推薦的預設範圍。它使子代理知識可透過版本控制共享。
* 要求子代理在開始工作前查詢其記憶："檢查此 PR，並檢查您的記憶以了解您之前看到的模式。"
* 要求子代理在完成任務後更新其記憶："既然您已完成，將您學到的內容儲存到您的記憶。" 隨著時間推移，這建立了一個知識庫，使子代理更有效。
* 直接在子代理的 markdown 檔案中包括記憶指示，以便它主動維護自己的知識庫：

  ```markdown theme={null}
  Update your agent memory as you discover codepaths, patterns, library
  locations, and key architectural decisions. This builds up institutional
  knowledge across conversations. Write concise notes about what you found
  and where.
  ```

#### 使用 hooks 的條件規則

為了更動態地控制工具使用，使用 `PreToolUse` hooks 在執行前驗證操作。當您需要允許工具的某些操作同時阻止其他操作時，這很有用。

此範例建立一個僅允許唯讀資料庫查詢的子代理。`PreToolUse` hook 在每個 Bash 命令執行前執行 `command` 中指定的指令碼：

```yaml theme={null}
---
name: db-reader
description: Execute read-only database queries
tools: Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-readonly-query.sh"
---
```

Claude Code [透過 stdin 將 hook 輸入作為 JSON 傳遞](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-input)給 hook 命令。驗證指令碼讀取此 JSON，提取 Bash 命令，並[以代碼 2 退出](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-2-behavior-per-event)以阻止寫入操作：

```bash theme={null}
#!/bin/bash
# ./scripts/validate-readonly-query.sh

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Block SQL write operations (case-insensitive)
if echo "$COMMAND" | grep -iE '\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE)\b' > /dev/null; then
  echo "Blocked: Only SELECT queries are allowed" >&2
  exit 2
fi

exit 0
```

在 macOS 和 Linux 上，使指令碼可執行，否則 hook 失敗而不是阻止任何內容：

```bash theme={null}
chmod +x ./scripts/validate-readonly-query.sh
```

若要測試規則，要求子代理執行 `UPDATE` 陳述式：指令碼以代碼 2 退出，Claude Code 阻止命令，子代理看到 `Blocked: Only SELECT queries are allowed` 訊息。

請參閱[Hook 輸入](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-input)以了解完整輸入架構，以及[退出代碼](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-output)以了解退出代碼如何影響行為。在 Windows 上，在 PowerShell 中編寫 hook 指令碼，並在 hook 條目中新增 `shell: powershell`，如[在 PowerShell 中執行 hooks](https://code.claude.com/docs/zh-TW/hooks.md#windows-powershell-tool)所示。

#### 禁用特定子代理

您可以透過在[設定](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings)中的 `deny` 陣列中新增子代理來防止 Claude 使用特定子代理。使用格式 `Agent(subagent-name)`，其中 `subagent-name` 符合子代理的 name 欄位。

```json theme={null}
{
  "permissions": {
    "deny": ["Agent(Explore)", "Agent(my-custom-agent)"]
  }
}
```

這適用於內建和自訂子代理。您也可以使用 `--disallowedTools` CLI 旗標：

```bash theme={null}
claude --disallowedTools "Agent(Explore)"
```

請參閱[權限文件](https://code.claude.com/docs/zh-TW/permissions.md#tool-specific-permission-rules)以了解更多有關權限規則的詳細資訊。

### 為子代理定義 hooks

子代理可以定義在子代理的生命週期期間執行的 [hooks](https://code.claude.com/docs/zh-TW/hooks.md)。有兩種方式設定 hooks：

* **在子代理的 frontmatter 中**：定義僅在該子代理活動時執行的 hooks
* **在 `settings.json` 中**：定義也在子代理內觸發的工作階段範圍 hooks。工具事件（例如 `PreToolUse` 和 `PostToolUse`）對子代理的工具呼叫觸發，與它們在主對話中的方式相同，`SubagentStart` 和 `SubagentStop` 在子代理啟動或完成時觸發

來自[設定檔、受管原則設定和 plugins](https://code.claude.com/docs/zh-TW/hooks.md#hook-locations)的 Hooks 都適用於子代理內，因此 `settings.json` 中的 `PreToolUse` hook 也在子代理使用的每個工具之前執行。

#### 子代理 frontmatter 中的 Hooks

直接在子代理的 markdown 檔案中定義 hooks。這些 hooks 僅在該特定子代理活動時執行，並在完成時清理。

> [!NOTE]
>
> Frontmatter hooks 在代理透過 Agent 工具或 @-mention 生成為子代理時觸發，以及當代理透過 [`--agent`](#invoke-subagents-explicitly) 或 `agent` 設定作為主工作階段執行時。在主工作階段情況下，它們與 [`settings.json`](https://code.claude.com/docs/zh-TW/hooks) 中定義的任何 hooks 一起執行。

若要讓專案層級 subagent 的 frontmatter hook 執行，請接受包含該 agent 檔案之資料夾的[工作區信任對話框](https://code.claude.com/docs/zh-TW/permissions.md#project-allow-rules-and-workspace-trust)。來自 `~/.claude/agents/` 中使用者層級 subagent 的 hook，以及來自您使用 `--agents` 傳遞之定義的 hook，無需此步驟即可執行。如果您使用 `--add-dir` 從受信任工作區的儲存庫之外新增資料夾，請另外信任該資料夾：其 `.claude/agents/` hook 不會繼承工作區的授權。

在您信任資料夾之前，subagent 仍會執行，但 Claude Code 會跳過其 frontmatter hook，並將說明如何信任該資料夾的錯誤記錄到除錯日誌。這是比設定檔中 hook 更嚴格的規則：信任父資料夾並不足夠，且 `-p` 工作階段不算作受信任。[在您信任資料夾前會執行的內容](https://code.claude.com/docs/zh-TW/permissions.md#what-runs-before-you-trust-a-folder)比較了這兩者。

所有[hook 事件](https://code.claude.com/docs/zh-TW/hooks.md#hook-events)都被支援。子代理最常見的事件是：

| 事件 | Matcher 輸入 | 何時觸發 |
| :- | :- | :- |
| `PreToolUse` | 工具名稱 | 子代理使用工具前 |
| `PostToolUse` | 工具名稱 | 子代理使用工具後 |
| `Stop` | （無） | 子代理完成時（在執行時轉換為 `SubagentStop`） |

此範例使用 `PreToolUse` hook 驗證 Bash 命令，並使用 `PostToolUse` 在檔案編輯後執行 linter：

```yaml theme={null}
---
name: code-reviewer
description: Review code changes with automatic linting
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-command.sh"
  PostToolUse:
    - matcher: "Edit|Write"
      hooks:
        - type: command
          command: "./scripts/run-linter.sh"
---
```

當代理作為子代理叫用時，frontmatter 中的 `Stop` hooks 自動轉換為 `SubagentStop` 事件。

#### 子代理事件的專案級 Hooks

在 `settings.json` 中設定 hooks，以回應主工作階段中的子代理生命週期事件。

| 事件 | Matcher 輸入 | 何時觸發 |
| :- | :- | :- |
| `SubagentStart` | 代理類型名稱 | 子代理開始執行時 |
| `SubagentStop` | 代理類型名稱 | 子代理完成時 |

兩個事件都支援 matchers 以按名稱針對特定代理類型。matcher 值是專案級和使用者級子代理的代理 frontmatter `name`，或 [plugin 子代理](https://code.claude.com/docs/zh-TW/plugins/components.md#agents)的 plugin 範圍識別碼，例如 `my-plugin:db-agent`。範圍名稱包含冒號，因此它被評估為[未錨定的正規表達式](https://code.claude.com/docs/zh-TW/hooks.md#matcher-patterns)；使用 `^` 和 `$` 錨定它，如 `^my-plugin:db-agent$`，以僅符合該代理。

此範例僅在 `db-agent` 子代理啟動時執行設定指令碼，並在任何子代理停止時執行清理指令碼：

```json theme={null}
{
  "hooks": {
    "SubagentStart": [
      {
        "matcher": "db-agent",
        "hooks": [
          { "type": "command", "command": "./scripts/setup-db-connection.sh" }
        ]
      }
    ],
    "SubagentStop": [
      {
        "hooks": [
          { "type": "command", "command": "./scripts/cleanup-db-connection.sh" }
        ]
      }
    ]
  }
}
```

請參閱 [Hooks](https://code.claude.com/docs/zh-TW/hooks.md) 以了解完整的 hook 設定格式。

## 使用 subagents

### 理解自動委派

Claude 根據您請求中的任務描述、subagent 設定中的 `description` 欄位和目前上下文自動委派任務。為了鼓勵主動委派，在 subagent 的 description 欄位中包括「use proactively」之類的短語。

保持描述簡潔：當您的 subagents 的合併描述超過 [15,000 個 token 限制](https://code.claude.com/docs/zh-TW/errors.md#agent-descriptions-are-over-the-15000-token-limit) 時，Claude Code 會顯示啟動警告，但仍會載入每個 subagent。

如果 subagent 隨附於 [外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md)，您可以測量 Claude 在貼近實際的提示詞中委派給它的可靠性，而不是一次檢查一個：[`claude plugin eval`](https://code.claude.com/docs/zh-TW/plugin-evals) 會在有和沒有外掛的情況下執行每個提示詞，並對結果進行評分。

### 明確呼叫 subagents

當自動委派不夠時，您可以自己要求 subagent。三種模式從一次性建議升級到工作階段範圍的預設：

* **自然語言**：在提示詞中命名 subagent；Claude 決定是否委派
* **@-mention**：保證 subagent 為一個任務執行
* **工作階段範圍**：整個工作階段透過 `--agent` 旗標或 `agent` 設定以該 subagent 的身分執行

對於自然語言，沒有特殊語法。命名 subagent，Claude 通常會委派：

```text wrap theme={null}
Use the test-runner subagent to fix failing tests
Have the code-reviewer subagent look at my recent changes
```

**@-mention subagent。** 輸入 `@` 並從預輸入中選擇 subagent，就像您 @-mention 檔案一樣。這確保該特定 subagent 執行，而不是將選擇留給 Claude：

```text wrap theme={null}
@"code-reviewer (agent)" look at the auth changes
```

您的完整訊息仍然會傳送給 Claude，它根據您要求的內容為 subagent 編寫任務提示詞。@-mention 控制 Claude 呼叫哪個 subagent，而不是它接收什麼提示詞。

由啟用的 [外掛](https://code.claude.com/docs/zh-TW/plugins/overview.md) 提供的 Subagents 在預輸入中顯示為其限定名稱，例如 `my-plugin:code-reviewer` 或 `my-plugin:review:security`（當外掛 [將 agents 組織到子資料夾](#choose-the-subagent-scope) 時）。目前在工作階段中執行的具名背景 subagents 也會出現在預輸入中，並在名稱旁邊顯示其狀態。

您也可以手動輸入提及而不使用選擇器：`@agent-<name>` 用於本地 subagents，或 `@agent-` 後跟外掛 subagents 的限定名稱，例如 `@agent-my-plugin:code-reviewer`。當您輸入此形式時，預輸入會顯示符合的檔案而不是 agents。agent 提及在您提交時仍會解析。

**將整個工作階段作為 subagent 執行。** 傳遞 [`--agent <name>`](https://code.claude.com/docs/zh-TW/cli-reference) 以啟動一個工作階段，其中主執行緒本身採用該 subagent 的工具限制和模型：

```bash theme={null}
claude --agent code-reviewer
```

除非 agent 的 [提示詞為空](#choose-the-subagent-scope)，否則自訂 subagent 的系統提示詞會完全取代預設的 Claude Code 系統提示詞，就像 [`--system-prompt`](https://code.claude.com/docs/zh-TW/cli-reference) 一樣。`CLAUDE.md` 檔案和專案記憶仍然透過正常訊息流載入，即使 agent 的定義設定了 [`omitClaudeMd`](#supported-frontmatter-fields)。如果您以具有自己提示詞的自訂 agent 身分使用 `-p` 執行工作階段，它也會在沒有 [git 狀態快照](https://code.claude.com/docs/zh-TW/settings-reference.md#includegitinstructions) 的情況下啟動。

agent 名稱在啟動標題中顯示為 `@<name>`，以便您可以確認它已啟用。

這適用於內建和自訂 subagents，選擇在您恢復工作階段時持續：Claude Code 會恢復 agent 的工具限制和模型以及對話。如果 agent 在您恢復時不再存在，工作階段會繼續使用預設工具，並顯示 [指出該 agent 名稱的警告](https://code.claude.com/docs/zh-TW/errors.md#session-agent-no-longer-available)。對於任一情況下的系統提示詞，請參閱 [已恢復對話中的系統提示詞旗標](https://code.claude.com/docs/zh-TW/cli-reference.md#system-prompt-flags-in-resumed-conversations)。

對於外掛提供的 subagent，您可以只傳遞 agent 名稱，Claude Code 會找到它：

```bash theme={null}
claude --agent security-reviewer
```

如果多個外掛提供具有相同名稱的 agents，傳遞限定名稱以消除歧義：

```bash theme={null}
claude --agent my-plugin:security-reviewer
```

如果外掛將 agent 放在其 `agents/` 目錄的子資料夾中，請在限定名稱中包括子資料夾，例如 `claude --agent my-plugin:review:security`。

若要使其成為專案中每個工作階段的預設值，請在 `.claude/settings.json` 中設定 `agent`：

```json theme={null}
{
  "agent": "code-reviewer"
}
```

如果兩者都存在，CLI 旗標會覆寫設定。

### 在前景或背景中執行 subagents

Subagents 可以在前景或背景中執行：

* **前景 subagents** 會阻擋主要對話直到完成。權限提示會在出現時傳遞給您。
* **背景 subagents** 在您繼續工作時並行執行。當背景 subagent 到達需要權限的工具呼叫時，Claude Code 會在您的主要工作階段中顯示提示，並指出提出請求的 subagent。核准以讓 subagent 繼續，或按 Esc 拒絕該單一工具呼叫而不停止 subagent。

#### 哪些 subagents 在背景中執行

在未進行任何設定的情況下，Claude 從您的主要對話產生的 subagent 會在背景中啟動。

* **`claude -p` 和 Agent SDK**：Claude 可以依自己的判斷或在您要求時等待。
* **您機器上的互動式終端機工作階段、VS Code 和桌面應用程式工作階段**：若要讓 Claude 等待 subagent，請 [關閉 fork 模式](#let-claude-wait-for-a-subagent)，該模式 [預設為開啟](#turn-fork-mode-on-or-off)。

對於具有 `context: fork` 的 skill，Claude Code 會改為遵循 [在 subagent 中執行 skills](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent) 中的規則，無論 fork 模式是否開啟。

#### 讓 Claude 等待 subagent

1. 將 `CLAUDE_CODE_FORK_SUBAGENT` 設定為 `0` 以關閉 [fork 模式](#turn-fork-mode-on-or-off)，例如在 [`settings.json`](https://code.claude.com/docs/zh-TW/settings) 中：

   ```json theme={null}
   {
     "env": {
       "CLAUDE_CODE_FORK_SUBAGENT": "0"
     }
   }
   ```

2. 從您的 shell 再次執行 `claude`，或開啟新的 VS Code 對話。

3. 當您需要先取得結果時，要求 Claude 等待，例如「run the reviewer subagent and wait for its report」。

若要在 Claude 等待時繼續工作，請在終端機中按 **Ctrl+B**，或在 VS Code 中按一下 [**Run in background**](https://code.claude.com/docs/zh-TW/vs-code.md#move-a-running-command-or-subagent-to-the-background)。

如果您將 [`CLAUDE_CODE_DISABLE_BACKGROUND_TASKS`](https://code.claude.com/docs/zh-TW/env-vars) 環境變數設定為 `1` 而不是關閉 fork 模式，Claude 會等待 subagents 完成後再繼續。背景命令也會關閉，且 **Ctrl+B** 不會將任何內容移至背景。

#### 背景 subagents 的工具、權限和結果

背景 subagents 執行時使用的 [內建工具集](#available-tools) 比前景 subagents 更小，除了對話 forks 和 [已恢復](#resume-subagents) 的前景 subagents。

背景 subagents 在您的主要工作階段中顯示每個權限提示。當您使用持續超過該單一工具呼叫的選擇（例如持續整個工作階段的授予）回答其中一個提示時，Claude Code 會將您的答案套用於整個工作階段，包括您的主要對話。

背景 subagent 可以讓背景 [Bash 或 PowerShell 命令](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands) [在其回合結束後繼續執行](https://code.claude.com/docs/zh-TW/interactive-mode.md#how-backgrounding-works)。當該命令結束時，Claude Code 會向 subagent 發送通知。

背景 subagent 的結果在稍後的回合中作為完成通知到達 Claude。Claude 在報告 subagent 的結果之前等待該通知，如果您先詢問進度，它會報告 subagent 仍在執行。

#### 面板和任務列表中已完成的 subagents

Claude Code 會根據 subagent 如何結束，以兩種方式之一清除提示輸入下方 subagent 面板中背景 subagent 的列：

* 當 subagent 成功完成時，Claude Code 會立即移除其列，並且除了在 [螢幕閱讀器模式](https://code.claude.com/docs/zh-TW/accessibility.md) 中之外，會在頁腳中顯示 `/tasks to see subagents` 30 秒。在這 30 秒內，執行 [`/tasks`](https://code.claude.com/docs/zh-TW/commands) 並在 subagent 上按 `Enter` 以開啟其逐字稿。在 v2.1.232 之前，Claude Code 在 subagent 完成後保持列 30 秒，與失敗的相同，且不顯示頁腳提示。
* 當 subagent 失敗或您停止它時，Claude Code 會保持其列 30 秒。若要更快清除列，請選擇它並按 `x`。

完成的背景 subagent 會保持列在 [`/tasks`](https://code.claude.com/docs/zh-TW/commands) 中，標記為完成並排序在執行中的工作下方，時間與頁腳提示相同，為 30 秒。其詳細檢視在 subagent 完成時保持開啟。失敗或您停止的 Subagents 會離開列表。在 v2.1.208 之前，完成的 subagent 在完成時立即離開列表，其詳細檢視關閉。

### Subagent 名稱

如果您在啟用 [agent teams](https://code.claude.com/docs/zh-TW/agent-teams.md#enable-agent-teams) 的情況下啟動工作階段，Claude 可以透過在 Agent 工具呼叫上傳遞 `name` 參數來給 subagent 命名。它可能會自行執行此操作，而不先詢問您。該名稱使 subagent 可定址：Claude 可以在完成後 [按名稱傳送訊息給它或恢復它](#resume-subagents)。

在啟用 [agent teams](https://code.claude.com/docs/zh-TW/agent-teams.md) 的互動式工作階段中，Claude 從主要對話產生的具有 `name` 的 subagent 會改為作為隊員啟動，除非呼叫是 [fork](#fork-the-current-conversation) 或在呼叫本身上傳遞 `isolation`。subagent 的 frontmatter 中的 `isolation` 值不會阻止此情況，隊員接著會在主要工作階段的工作目錄中執行。請參閱 [Claude 如何啟動 agent teams](https://code.claude.com/docs/zh-TW/agent-teams.md#how-claude-starts-agent-teams)。

### Subagents 中的 API 錯誤

當某些東西 [在中途切斷 subagent 的回應](https://code.claude.com/docs/zh-TW/errors.md#the-response-above-may-be-incomplete)，且部分回應包含文字但沒有工具呼叫時，Claude Code 會提示 subagent 繼續而不是結束執行。這也發生在互動式工作階段中。執行僅在這些延續用完時才因錯誤而結束。

subagent 的執行因 API 錯誤（例如用量上限或重複的伺服器錯誤）而結束時，會將該失敗報告回 Claude。Claude 接收的內容取決於 subagent 執行的位置：

* **前景**：如果速率限制、過載或伺服器錯誤切斷已經產生文字輸出的 subagent，Agent 工具會返回該部分輸出，並附註 subagent 被切斷且未完成其任務。未產生任何內容或其唯一輸出為工具呼叫的 subagent 會失敗，並顯示 [`Agent terminated early due to an API error`](https://code.claude.com/docs/zh-TW/errors#agent-terminated-early-due-to-an-api-error)，後跟錯誤詳細資訊。
* **背景**：subagent 被標記為失敗，Claude 在其結束時接收的訊息會指出 API 錯誤並包括 subagent 的最後輸出，所以部分工作不會遺失。

如果 subagent 的報告以下列這行開頭，表示該 subagent 是在備援模型上完成的：

```text theme={null}
⚠ This agent switched to <model> because its earlier model could not be used.
```

當您設定 [備援模型鏈](https://code.claude.com/docs/zh-TW/model-config.md#fallback-model-chains) 且 subagent 遇到鏈涵蓋的失敗（例如其模型不可用）時，Claude Code 會將 subagent 切換到鏈中接受請求的第一個模型。Subagent 會繼續工作而不是因錯誤而結束。

一旦底層 API 錯誤清除，要求 Claude 重試任務或 [恢復 subagent](#resume-subagents)。

### Subagent 輸出掃描

Claude Code 在 Claude 讀取 subagent 的最終報告之前掃描它。Subagent 可能已讀取您從未審查過的檔案、網頁或命令輸出，這些來源的文字可能包含針對主要對話的指令。掃描永遠不會移除或改寫任何內容；它會進行您可能在報告中注意到的兩種更改：

* **反斜線插入**：掃描會在模仿 Claude Code 自己輸出的文字中插入反斜線，例如 `<system-reminder>` 標籤或以 `Human:` 或 `Assistant:` 開頭的行，以便模仿讀作普通文字而不是被誤認為是對話的一部分。
* **標記行**：當報告模仿 `<system-reminder>` 之類的標籤或提及 `bypassPermissions` 或 `--dangerously-skip-permissions` 之類的權限設定時，掃描會前置以 `[harness: subagent output matched instruction-shaped pattern(s):` 開頭的行。權限設定提及會獲得標記行，但文字本身保持原樣。

掃描不會判斷內容是否惡意，也不會改變報告中的指令可以做什麼：報告導致 Claude 進行的工具呼叫仍然會通過工作階段的 [權限檢查](https://code.claude.com/docs/zh-TW/permissions.md) 和 [沙箱機制](https://code.claude.com/docs/zh-TW/sandboxing.md)。它不是 [限制 subagent 可以存取的內容](#control-subagent-capabilities) 的替代品。

一份返回給 Claude 作為 subagent 結果的報告也會在標題下到達，該標題將其標記為 subagent 輸出。標題說明報告中的指令或核准聲明是 subagent 的言論，不具有來自您的任何授權。

[背景 subagent 的報告](#run-subagents-in-foreground-or-background) 到達完成通知內，該通知被標記為自動化事件而不是來自您的訊息。

### 常見模式

#### 隔離高容量操作

subagents 最有效的用途之一是隔離產生大量輸出的操作。執行測試、獲取文件或處理日誌檔案可能會消耗大量上下文。透過將這些委派給 subagent，詳細輸出保留在 subagent 的上下文中，而只有相關摘要返回到主要對話。

```text wrap theme={null}
Use a subagent to run the test suite and report only the failing tests with their error messages
```

#### 執行並行研究

對於獨立調查，產生多個 subagents 以同時工作：

```text wrap theme={null}
Research the authentication, database, and API modules in parallel using separate subagents
```

每個 subagent 獨立探索其領域，然後 Claude 綜合發現。當研究路徑彼此不相依時，這效果最好。

> [!WARNING]
>
> 當 subagents 完成時，其結果返回到主要對話。執行許多 subagents，每個都返回詳細結果，可能會消耗大量上下文，每個 subagent 在執行時會花費自己的 tokens。

對於需要持續並行執行或不適合一個上下文視窗的工作，請在 [個別工作階段](https://code.claude.com/docs/zh-TW/agents.md) 中執行它，並讓 Claude [在它們之間傳遞發現](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)。

#### 鏈接 subagents

對於多步驟工作流程，要求 Claude 按順序使用 subagents。每個 subagent 完成其任務並將結果返回給 Claude，然後將相關上下文傳遞給下一個 subagent。

```text wrap theme={null}
Use the code-reviewer subagent to find performance issues, then use the optimizer subagent to fix them
```

### 在 subagents 和主要對話之間選擇

在以下情況下使用 **主要對話**：

* 任務需要頻繁的來回或反覆改進
* 多個階段共享重要上下文，例如規劃、實作和測試
* 您正在進行快速、有針對性的更改
* 延遲很重要。不是 [fork](#fork-the-current-conversation) 的 subagent 從頭開始，可能需要時間收集上下文

在以下情況下使用 **subagents**：

* 任務產生您不需要在主要上下文中的詳細輸出
* 您想強制執行特定的工具限制或權限
* 工作是自包含的，可以返回摘要

當您想要可重複使用的提示詞或在主要對話上下文中執行的工作流程而不是隔離的 subagent 上下文時，請改為考慮 [Skills](https://code.claude.com/docs/zh-TW/skills.md)。

對於關於對話中已有內容的問題，請使用 [`/btw`](https://code.claude.com/docs/zh-TW/interactive-mode#side-questions-with-%2Fbtw) 而不是 subagent。它沒有工具存取，答案不會新增到歷史記錄。

### 讓 subagents 產生自己的 subagents

預設情況下，subagent 可以產生自己的 subagents，最多在主要對話下方三層。在深度限制處，Claude Code 會從除 [fork](#fork-the-current-conversation) 外的每個 subagent 中扣留 `Agent` 工具，所以限制處的 subagent 會自行執行委派的工作並返回一個摘要。fork 在限制處保持其繼承的工具列表中的 `Agent`，但工具會返回錯誤而不是產生。

巢狀 subagents 適合本身會分裂成並行子任務的委派任務，例如審查者 subagent 為每個發現分派驗證者。預設情況下，進行產生的 subagent 會等待每個巢狀 subagent 的報告：

* **互動式終端機工作階段**：只有頂層 subagent 的摘要會返回給您，因為產生背景 subagents 的 subagent 在完成之前會等待其結果。
* **`claude -p` 和 Agent SDK**：當 [fork 模式](#turn-fork-mode-on-or-off) 開啟時，進行產生的 subagent 會等待。如果您關閉 fork 模式，巢狀 subagents 會改為在 [背景](#run-subagents-in-foreground-or-background) 中啟動。進行產生的 subagent 不會等待背景巢狀 subagent，若該巢狀 subagent 比進行產生的 subagent 存續得更久，它會向您的主要對話報告。

若要改變限制，請將 [`CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`](https://code.claude.com/docs/zh-TW/env-vars) 設定為您想要在主要對話下方的 subagent 層數。例如，[`settings.json`](https://code.claude.com/docs/zh-TW/settings) 中的此項目將巢狀限制為兩層：

```json theme={null}
{
  "env": {
    "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH": "2"
  }
}
```

使用此值，您的 subagents 可以委派給自己的第二層，該第二層無法進一步委派。設定 `1` 以關閉巢狀。

巢狀 subagent 的設定方式與頂層 subagent 相同，並從相同的 [範圍](#choose-the-subagent-scope) 解析。若要在巢狀開啟時防止某個 subagent 產生 subagents，例如應保持唯讀的審查者，請從其 [`tools`](#available-tools) 列表中省略 `Agent` 或將其新增到 `disallowedTools`。

在終端機中，Claude Code 會在提示輸入下方的 subagent 面板中將巢狀 subagents 顯示為樹狀結構，並用 `(+N)` 計數標記面板中仍有後代的每一列。開啟一列以查看該 subagent 的同級和直接子代，以及返回到 `main` 的路徑。

### 並行 subagent 限制

兩個限制控制 subagent 使用，每個都有自己的變數：這個限制阻止 Claude 在太多 subagents 執行時產生更多 subagents，[深度限制](#let-subagents-spawn-their-own-subagents) 限制 subagents 巢狀的深度。對於 Claude 在工作階段中可以產生的 subagents 總數沒有限制。

預設情況下，當 20 個 subagents 在工作階段中執行時，使用 Agent 工具產生另一個會失敗，並顯示 `Concurrent subagent limit reached`，錯誤告訴 Claude 不要重試。當執行計數降至限制以下時，產生再次成功。若要改變限制，請將 [`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`](https://code.claude.com/docs/zh-TW/env-vars) 設定為任何正整數。啟用 [ultracode](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level) 的工作階段被豁免：限制在那裡不被強制執行。需要 Claude Code v2.1.217 或更新版本。

限制僅阻止 Claude 使用 Agent 工具產生的 subagents，但其他執行佔用相同的插槽：

* 您使用 [`/subtask`](#fork-the-current-conversation) 啟動的工作階段內 fork 在執行時佔用一個插槽，永遠不會被限制阻止。
* [恢復已完成的 subagent](#resume-subagents) 會佔用一個新插槽而不檢查限制，所以恢復可以將執行計數推過限制。

其他功能執行的 agents，例如 [工作流程](https://code.claude.com/docs/zh-TW/workflows.md) agents 和 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員，則遵循自己的限制。

### 管理 subagent 上下文

#### 啟動時載入的內容

每個 subagent 都以全新、隔離的上下文視窗開始。它看不到您的對話歷史記錄、您已經呼叫的 skills 或 Claude 已經讀取的檔案。Claude 撰寫一條委派訊息來總結任務，subagent 從那裡開始工作。例外是 [fork](#fork-the-current-conversation)，它繼承父對話而不是從頭開始。

非 fork subagent 的初始上下文包含：

* **系統提示詞**：agent 自己的提示詞加上 Claude Code 附加的環境詳細資訊，而不是 Claude Code 系統提示詞。自訂 subagents 在 [markdown 正文](#write-subagent-files) 或 `prompt` 欄位中定義它們。內建 agents 有預定義的提示詞。
* **任務訊息**：Claude 在交接工作時編寫的委派提示詞。
* **CLAUDE.md 檔案**：主要對話載入的 [CLAUDE.md 層級](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load) 的每個級別，包括 `~/.claude/CLAUDE.md`、專案規則、`CLAUDE.local.md`、受管理的政策檔案和任何作為專案指令載入的 [`AGENTS.md` 檔案](https://code.claude.com/docs/zh-TW/memory#agents-md)。內建的 Explore 和 Plan agents 跳過這個。定義中設定 [`omitClaudeMd`](#supported-frontmatter-fields) 的 subagent 只載入受管理的政策檔案，或當定義來自 [受管設定](#choose-the-subagent-scope) 時完全不載入。
* **Git 狀態**：Claude Code 在 subagent 啟動時從您的儲存庫讀取的快照。對於在該儲存庫的 [自己的 worktree](https://code.claude.com/docs/zh-TW/worktrees.md#isolate-subagents-with-worktrees) 中執行的 subagent，快照會顯示該 worktree 的分支、狀態和最近的提交。在 Git 儲存庫之外或快照被關閉時不存在；請參閱 [`includeGitInstructions`](https://code.claude.com/docs/zh-TW/settings-reference#includegitinstructions)。Explore 和 Plan 無論如何都跳過它。
* **預載入的 skills**：agent 的 [`skills` 欄位](#preload-skills-into-subagents) 中命名的任何 skill 的完整內容。內建 agents 不預載入 skills。
* **同級名單**：一則 [系統提醒](https://code.claude.com/docs/zh-TW/glossary.md#system-reminder)，列出 `main` 和工作階段中的每個其他具名 agent，每個都是 [`SendMessage`](#resume-subagents) 的有效 `to` 值。名單僅在 subagent 的工具包括 `SendMessage` 且至少有一個其他 agent 有名稱時出現，無論是 Claude 在產生時為它命名，還是它作為 [agent team](https://code.claude.com/docs/zh-TW/agent-teams.md) 隊員執行。它是在 subagent 啟動時拍攝的快照，所以稍後命名的 agents 不會出現。

若要啟動您自己的 subagents 而不載入使用者、專案和本地 CLAUDE.md 檔案，請在其 frontmatter 或 `--agents` JSON 中設定 [`omitClaudeMd: true`](#supported-frontmatter-fields)。對於 Explore、Plan 和設定了 `omitClaudeMd` 的 subagents，當 subagent 處理某個子目錄中的檔案時，該子目錄的 `CLAUDE.md` 和相符的 [路徑範圍規則](https://code.claude.com/docs/zh-TW/memory.md#path-specific-rules) 仍會 [載入](https://code.claude.com/docs/zh-TW/memory.md#how-claude-md-files-load)。

主要對話在讀取這些 subagents 的結果時仍然擁有您的完整 CLAUDE.md，所以大多數規則不需要傳達到 subagent 本身。如果某條規則必須傳達，例如「忽略 `vendor/` 目錄」，請在您委派時給 Claude 的提示詞中重新陳述它。

您無法改變哪些 subagents 接收 git 狀態。只有 Explore 和 Plan 跳過它。

某些主要對話狀態永遠不會到達非 fork subagent：

* **輸出風格**：subagent 執行自己的系統提示詞，所以您的 [輸出風格](https://code.claude.com/docs/zh-TW/output-styles.md) 不會塑造其回應，除了在 [fork](#fork-the-current-conversation) 中。
* **自動記憶**：主要對話的 [自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory) 不會被載入。若要給 subagent 自己的持久記憶，請使用 [`memory` 欄位](#enable-persistent-memory)。
* **上下文視窗大小**：subagent 的上下文視窗大小由其自己的模型決定，而不是父級的。委派給具有較小視窗的模型會給該 subagent 較小的視窗。

#### 恢復 subagents

每個 subagent 呼叫都會建立一個新實例而不是繼續較早的實例。若要繼續現有 subagent 的工作而不是重新開始，請要求 Claude 恢復它。

恢復的 subagents 保留其完整對話歷史記錄，包括所有先前的工具呼叫、結果和推理。如果 subagent 產生了 [自己的背景 subagents](#let-subagents-spawn-their-own-subagents)，該歷史記錄包括它執行時它們傳遞的結果。在 v2.1.304 之前，Claude 在 subagent 完成後立即傳送訊息或恢復的 subagent 可能會忘記其最近的工作。

* 當 subagent 完成時，Claude 接收其 agent ID。
* 內建的 Explore 和 Plan agents 是一次性的，不返回 agent ID，所以 Claude 無法恢復它們。當您需要繼續工作時，請使用 `general-purpose` 或自訂 subagent。
* 當 subagent 在其 [`maxTurns`](#supported-frontmatter-fields) 限制處停止時，Claude Code 會將返回的輸出標記為部分，Claude 可以恢復該 subagent 以繼續其工作。

Claude 使用 `SendMessage` 工具，將 agent 的 ID 或名稱作為 `to` 欄位來恢復它。`SendMessage` 不需要啟用 [agent teams](https://code.claude.com/docs/zh-TW/agent-teams.md)；只有結構化的團隊協定訊息，例如 `shutdown_request` 和 `plan_approval_response`，才需要啟用。除了 subagents 和隊員，在啟用跨工作階段訊息的工作階段中，Claude 可以使用相同的工具傳送訊息給 [您的其他 Claude Code 工作階段](https://code.claude.com/docs/zh-TW/cross-session-messaging.md)，無論是在此機器上或 [其他機器上](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#message-sessions-on-other-machines)。

若要恢復 subagent，請要求 Claude 繼續先前的工作：

```text wrap theme={null}
Use the code-reviewer subagent to review the authentication module
[Agent completes]

Continue that code review and now analyze the authorization logic
[Claude resumes the subagent with full context from previous conversation]
```

當 Claude 使用 `SendMessage` 工具向已完成的 subagent 發送訊息時，subagent 在背景中恢復，無需新的 `Agent` 呼叫。同樣適用於 Claude 使用 `TaskStop` 工具停止的 subagent，一旦其停止的執行已退出。恢復的執行保持 [subagent 首次執行時的工具集](#run-subagents-in-foreground-or-background)，並可以繼續讀取 [原始執行預熱的提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#subagents-and-the-cache)。

具有 `SendMessage` 工具的 subagent 也可以發送該訊息。在互動式工作階段中，恢復的 agent 接著會向恢復它的 subagent 報告，而不是您的主要對話。該 subagent 在完成自己的工作之前等待結果。當 subagent 傳送訊息給它所報告的 agent（例如自己的啟動者）時，Claude Code 會恢復該 agent 而不重新導向其結果。

您自己停止的 subagent，使用 `/tasks` 中的 `x` 或 SDK `stop_task` 請求，不會自動恢復。如果 Claude 向它發送訊息，訊息會被拒絕，Claude 會被告知該 agent 已被取消。

當 [該 subagent 的列仍在 subagent 面板中](#run-subagents-in-foreground-or-background) 時，在其逐字稿中輸入以自己恢復它。之後，來自 Claude 的訊息可以再次自動恢復它。

恢復會在相同 ID 下啟動 agent 的新執行，所以已經失敗或完成的 subagent 在任務列表和 Agent SDK 的任務事件中再次顯示為執行中。

`SendMessage` 會檢查名稱是否仍然指向它在對話中較早時到達的同一 agent。如果較新的 agent 已取得該名稱，例如重新產生的背景 agent 重複使用了它，Claude Code 會拒絕發送，而不是將其傳遞給錯誤的 agent，錯誤會報告該名稱現在到達的 agent，以便 Claude 可以重新指定目標。若要在較早的 agent 仍在執行時到達它，Claude 會透過產生該 agent 時收到的 agent ID 來定址它。檢查的範圍是目前對話，並在 `/clear` 時重置。

subagent 將來自啟動它的 agent 的訊息視為正常任務指示，包括任務中途的方向修正，並在其自己的權限設定內據以行動。無論誰發送訊息，兩個限制仍然成立：來自任何 agent 的任何訊息都不計為您對待處理權限提示的核准，任何 agent 訊息都無法改變 subagent 的權限設定、`CLAUDE.md` 或設定。只有權限系統或您自己的訊息可以授予核准。

如果您想明確參考 agent ID，也可以要求 Claude 提供，或在 `~/.claude/projects/{project}/{sessionId}/subagents/` 的逐字稿檔案中找到 ID。每個逐字稿都儲存為 `agent-{agentId}.jsonl`。

Subagent 逐字稿獨立於主要對話持續存在：

* **主要對話壓縮**：當主要對話壓縮時，subagent 逐字稿不受影響。它們儲存在單獨的檔案中。
* **工作階段持續性**：Subagent 逐字稿在其工作階段內持續存在。您可以透過恢復相同工作階段在重新啟動 Claude Code 後 [恢復 subagent](#resume-subagents)。
* **自動清理**：Claude Code 在 `cleanupPeriodDays` 保留期後刪除 subagent 逐字稿，預設為 30 天，遵循 [保留掃描規則](https://code.claude.com/docs/zh-TW/claude-directory.md#cleaned-up-automatically)。

##### 重新啟動後按名稱傳送訊息給 subagent

> [!NOTE]
>
> 對於以隊員身分啟動的 subagent，請改為參閱 [agent team 限制](https://code.claude.com/docs/zh-TW/agent-teams.md#limitations)。

如果在您重新啟動 Claude Code 並恢復工作階段後，Claude 無法按名稱傳送訊息給 subagent，請改為將該 subagent 的 agent ID 提供給 Claude。Claude 自上次 [壓縮](https://code.claude.com/docs/zh-TW/context-window.md#what-survives-compaction) 以來從主要對話所給的名稱會在重新啟動後保留。該次壓縮之前的名稱則不會保留。若要找出某個名稱對應的 ID，請在 `~/.claude/projects/{project}/{sessionId}/subagents/` 中的 `agent-{agentId}.meta.json` 檔案裡尋找該名稱。

透過 ID 傳送一則訊息後，subagent 的名稱會再次生效，除非較新的 agent 已取得該名稱。在 v2.1.299 之前，沒有任何名稱能在重新啟動後保留，且即使 agent ID 仍然有效，按名稱傳送也會被拒絕。

#### 自動壓縮

Subagents 支援自動壓縮。壓縮會在 subagent 自己的上下文視窗填滿時觸發，`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` 也適用於 subagents。請參閱 [環境變數](https://code.claude.com/docs/zh-TW/env-vars.md) 以了解覆寫何時生效。

壓縮事件記錄在 subagent 逐字稿檔案中：

```json theme={null}
{
  "type": "system",
  "subtype": "compact_boundary",
  "compactMetadata": {
    "trigger": "auto",
    "preTokens": 167189
  }
}
```

`preTokens` 值顯示壓縮發生前使用了多少個 tokens。

##### 為單一 subagent 設定自動壓縮視窗

若要讓某個 subagent 比原本更早壓縮，請在其 [frontmatter](#supported-frontmatter-fields) 中將 `autoCompactWindow` 設定為介於 `100000` 到 `1000000` 之間的 token 數。如果您設定了 [`CLAUDE_CODE_AUTO_COMPACT_WINDOW`](https://code.claude.com/docs/zh-TW/env-vars#variables)，subagent 會改用該變數的視窗，此欄位不會生效，除非 Claude Code [忽略了該變數的值](https://code.claude.com/docs/zh-TW/model-config.md#claude_code_auto_compact_window-values)。需要 Claude Code v2.1.296 或更新版本。

以下 frontmatter 為讀取長日誌檔案的 subagent 將 `autoCompactWindow` 設定為 200,000 個 tokens：

```yaml theme={null}
---
name: log-reader
description: Reads long log files and reports the errors it finds
autoCompactWindow: 200000
---
```

請將值寫成純整數，例如 `200000`，因為在 frontmatter 中 Claude Code 會將 `200k` 讀取為 200，這超出了允許的範圍。subagent 仍會載入，並像該欄位不存在一樣進行壓縮。若要檢查 Claude Code 是否忽略了您的值，請在 shell 中執行 `claude --debug`，並在 [偵錯日誌](#supported-frontmatter-fields) 中搜尋 `invalid autoCompactWindow`。

如果值在範圍內但您仍未看到任何變化，請檢查以下原因：

* **該值未低於 subagent 原本會繼承的 [自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#context-window-and-auto-compaction)**：若要更早壓縮，請設定低於該視窗的值。
* **您使用 `--agent` 或 `agent` 設定以此 subagent 的身分執行整個工作階段**：此欄位在該情況下不會生效。若要設定工作階段的視窗，請參閱 [設定自動壓縮視窗](https://code.claude.com/docs/zh-TW/model-config.md#set-the-auto-compact-window)。

## Fork 目前的對話

> [!NOTE]
>
> 當[agent 檢視已關閉](https://code.claude.com/docs/zh-TW/agent-view.md#turn-off-agent-view)時，`/subtask` 無法使用，`/fork` 會改為啟動 forked subagent；否則 `/fork` 會將整個工作階段複製到新的[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#from-inside-a-session)。

Fork 是一個 subagent，它繼承到目前為止的整個對話，而不是從頭開始。這會放棄 subagents 否則提供的輸入隔離：fork 看到與主工作階段相同的系統提示、工具、模型和訊息歷史記錄，因此您可以將側面任務交給它，而無需重新解釋情況。Fork 自己的工具呼叫仍然保持在您的對話之外，只有其最終結果返回，因此您的主要上下文視窗保持乾淨。當任何其他 subagent 需要太多背景才能有用時，或當您想從相同的起點並行嘗試多種方法時，使用 fork。

在 fork 模式開啟期間（預設即為開啟），Claude 可以自行啟動 fork。若要停止 fork，請參閱[關閉 fork 模式](#turn-fork-mode-on-or-off)。

您可以使用 `/subtask` 後跟任務自己啟動 fork，無論 fork 模式是否啟用。Claude Code 從任務的前幾個詞命名 fork。以下範例 forks 對話以在您在主工作階段中繼續實現時草擬測試案例：

```text wrap theme={null}
/subtask draft unit tests for the parser changes so far
```

Fork 出現在提示下方的面板中，並在您繼續工作時在背景中執行。完成後，其結果作為訊息到達您的主要對話。下一部分涵蓋面板控制項，用於在 forks 執行時觀察和引導它們。

### 觀察和引導執行中的 forks

執行中的 forks 出現在提示輸入下方的面板中，主工作階段有一行，每個 fork 有一行。

當 fork 成功完成時，Claude Code 會移除其行。Claude Code 會保留失敗或您停止的 fork 的行 30 秒，[與任何其他背景 subagent 相同](#run-subagents-in-foreground-or-background)。在 v2.1.232 之前，Claude Code 也會將完成的 fork 的行保留 30 秒。

使用這些鍵與面板互動：

| Key | Action |
| :- | :- |
| `↑` / `↓` | 在行之間移動 |
| `Enter` | 開啟選定 fork 的文字記錄並向其發送後續訊息 |
| `x` | 停止執行中的選定 fork，或如果不再執行則關閉其行。在主工作階段行或使用 `Enter` 開啟其文字記錄的 fork 行上，`x` 會改為輸入到提示中 |
| `Esc` | 將焦點返回到提示輸入 |

開啟 fork 或 subagent 的逐字稿時，後續訊息和 [skills](https://code.claude.com/docs/zh-TW/skills.md) 會傳送到該 agent。在 Claude Code v2.1.314 或更新版本中，[`/btw`](https://code.claude.com/docs/zh-TW/interactive-mode#ask-btw-about-a-subagent) 會根據開啟的逐字稿回答。其他內建命令則會傳送到您的主要對話，並具有以下保護措施：

* `/compact`、`/clear` 和 `/rewind` 會作用於主要對話，因此從此檢視執行其中任一命令之前，Claude Code 會要求您確認。
* `/model` 和 `/fast` 會設定主要對話的模型和快速模式，而不是所檢視 agent 的，因此無法從此檢視執行。系統會顯示通知說明原因。

若要讓所檢視的 agent 在其等待的工作完成之前讀取您的訊息，請使用 [`Ctrl+Enter` 或 `Ctrl+X Ctrl+S`](https://code.claude.com/docs/zh-TW/keybindings#chat-actions) 傳送。該 agent 正在等待的任何可移至[背景](https://code.claude.com/docs/zh-TW/tools-reference.md#background-commands)的 shell 命令或 subagent 都會移至背景並繼續執行。當 agent 正在撰寫回應，或正在等待無法移至背景的工作時，它會繼續進行，並在該工作完成後讀取您的訊息。需要 Claude Code v2.1.286 或更新版本。

### Forks 與其他 subagents 的區別

Fork 繼承主工作階段在產生時擁有的所有內容。任何其他 subagent 從其定義開始新鮮。

| | Fork | 非 fork subagent |
| :- | :- | :- |
| Context | 完整對話歷史記錄 | 新鮮上下文，帶有您傳遞的提示 |
| 系統提示和工具 | 與主工作階段相同 | 來自 subagent 的[定義檔](#write-subagent-files)，[針對背景執行進行篩選](#available-tools) |
| Model | 與主工作階段相同 | 來自 subagent 的 `model` 欄位 |
| Prompt cache | 與主工作階段共享 | 單獨的快取 |

因為 fork 的系統提示詞和工具定義與父級相同，其第一個請求重複使用父級的[提示快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#subagents-and-the-cache)。由於這種重複使用，對於需要相同上下文的任務，fork 的成本比新的 subagent 更低。

當 Claude 透過 Agent 工具產生 fork 時，它可以傳遞 `isolation: "worktree"`，以便 fork 的檔案編輯被寫入單獨的 git worktree 而不是您的簽出。Fork 無法產生進一步的 forks。

### 關閉 fork 模式

Fork 模式讓 Claude 能夠自行啟動 fork。若要阻止 Claude 啟動 fork：

* **僅停止 fork**：在您的[設定](#disable-specific-subagents)中將 `"Agent(fork)"` 新增至 `permissions.deny`。
* **關閉 fork 模式**：依照[讓 Claude 等待 subagent](#let-claude-wait-for-a-subagent) 中的步驟，將 `CLAUDE_CODE_FORK_SUBAGENT` 設定為 `0`。

在 fork 模式開啟期間，Claude 在您電腦上的互動式終端機、VS Code 或桌面工作階段中也無法[等待 subagent](#run-subagents-in-foreground-or-background)。從 Claude Code v2.1.302 起，fork 模式預設為開啟；在互動式終端機工作階段中，則從 v2.1.232 起預設為開啟。

## 範例 subagents

這些範例展示了建立 subagents 的有效模式。將它們用作起點，或使用 Claude 生成自訂版本。

> [!TIP]
>
> **最佳實踐：**
>
> * **設計專注的 subagents：** 每個 subagent 應該在一個特定任務上表現出色
> * **撰寫詳細的描述：** Claude 使用描述來決定何時委派。讓每個描述具體到足以路由到正確的 subagent，並將組合集合保持在 [15,000 個 token 描述預算](#understand-automatic-delegation) 內
> * **限制工具存取：** 僅授予必要的權限以確保安全和專注
> * **簽入版本控制：** 與您的團隊共享專案 subagents

### 程式碼審查者

一個唯讀 subagent，審查程式碼而不修改它。此範例展示如何設計一個具有有限工具存取（無 Edit 和 Write）和詳細提示的專注 subagent，該提示明確指定要查找的內容以及如何格式化輸出。

```markdown theme={null}
---
name: code-reviewer
description: Expert code review specialist. Proactively reviews code for quality, security, and maintainability. Use immediately after writing or modifying code.
tools: Read, Grep, Glob, Bash
model: inherit
---

You are a senior code reviewer ensuring high standards of code quality and security.

When invoked:
1. Run git diff to see recent changes
2. Focus on modified files
3. Begin review immediately

Review checklist:
- Code is clear and readable
- Functions and variables are well-named
- No duplicated code
- Proper error handling
- No exposed secrets or API keys
- Input validation implemented
- Good test coverage
- Performance considerations addressed

Provide feedback organized by priority:
- Critical issues (must fix)
- Warnings (should fix)
- Suggestions (consider improving)

Include specific examples of how to fix issues.
```

### 除錯器

一個可以分析和修復問題的 subagent。與程式碼審查者不同，這個包括 Edit，因為修復錯誤需要修改程式碼。提示提供了從診斷到驗證的清晰工作流程。

```markdown theme={null}
---
name: debugger
description: Debugging specialist for errors, test failures, and unexpected behavior. Use proactively when encountering any issues.
tools: Read, Edit, Bash, Grep, Glob
---

You are an expert debugger specializing in root cause analysis.

When invoked:
1. Capture error message and stack trace
2. Identify reproduction steps
3. Isolate the failure location
4. Implement minimal fix
5. Verify solution works

Debugging process:
- Analyze error messages and logs
- Check recent code changes
- Form and test hypotheses
- Add strategic debug logging
- Inspect variable states

For each issue, provide:
- Root cause explanation
- Evidence supporting the diagnosis
- Specific code fix
- Testing approach
- Prevention recommendations

Focus on fixing the underlying issue, not the symptoms.
```

### 資料科學家

一個用於資料分析工作的特定領域 subagent。此範例展示如何為典型編碼任務之外的專門工作流程建立 subagents。它明確設定 `model: sonnet` 以進行更有能力的分析。

```markdown theme={null}
---
name: data-scientist
description: Data analysis expert for SQL queries, BigQuery operations, and data insights. Use proactively for data analysis tasks and queries.
tools: Bash, Read, Write
model: sonnet
---

You are a data scientist specializing in SQL and BigQuery analysis.

When invoked:
1. Understand the data analysis requirement
2. Write efficient SQL queries
3. Use BigQuery command line tools (bq) when appropriate
4. Analyze and summarize results
5. Present findings clearly

Key practices:
- Write optimized SQL queries with proper filters
- Use appropriate aggregations and joins
- Include comments explaining complex logic
- Format results for readability
- Provide data-driven recommendations

For each analysis:
- Explain the query approach
- Document any assumptions
- Highlight key findings
- Suggest next steps based on data

Always ensure queries are efficient and cost-effective.
```

### 資料庫查詢驗證器

一個允許 Bash 存取但驗證命令以僅允許唯讀 SQL 查詢的 subagent。此範例展示如何在需要比 `tools` 欄位提供的更精細控制時使用 `PreToolUse` hooks。

```markdown theme={null}
---
name: db-reader
description: Execute read-only database queries. Use when analyzing data or generating reports.
tools: Bash
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "./scripts/validate-readonly-query.sh"
---

You are a database analyst with read-only access. Execute SELECT queries to answer questions about the data.

When asked to analyze data:
1. Identify which tables contain the relevant data
2. Write efficient SELECT queries with appropriate filters
3. Present results clearly with context

You cannot modify data. If asked to INSERT, UPDATE, DELETE, or modify schema, explain that you only have read access.
```

Claude Code [透過 stdin 將 hook 輸入作為 JSON 傳遞](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-input) 給 hook 命令。驗證指令碼讀取此 JSON，提取正在執行的命令，並根據 SQL 寫入操作清單檢查它。如果檢測到寫入操作，指令碼 [以代碼 2 退出](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-2-behavior-per-event) 以阻止執行並透過 stderr 向 Claude 返回錯誤訊息。

在專案中的任何位置建立驗證指令碼。路徑必須與 hook 配置中的 `command` 欄位相符：

```bash theme={null}
#!/bin/bash
# Blocks SQL write operations, allows SELECT queries

# Read JSON input from stdin
INPUT=$(cat)

# Extract the command field from tool_input using jq
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [ -z "$COMMAND" ]; then
  exit 0
fi

# Block write operations (case-insensitive)
if echo "$COMMAND" | grep -iE '\b(INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|REPLACE|MERGE)\b' > /dev/null; then
  echo "Blocked: Write operations not allowed. Use SELECT queries only." >&2
  exit 2
fi

exit 0
```

在 macOS 和 Linux 上，使指令碼可執行：

```bash theme={null}
chmod +x ./scripts/validate-readonly-query.sh
```

在 Windows 上，使用 PowerShell 編寫驗證指令碼，並將 `shell: powershell` 新增至 hook 項目。請參閱 [在 PowerShell 中執行 hooks](https://code.claude.com/docs/zh-TW/hooks.md#windows-powershell-tool)。

Hook 透過 stdin 接收 JSON，Bash 命令在 `tool_input.command` 中。退出代碼 2 阻止操作並將錯誤訊息反饋給 Claude。請參閱 [Hooks](https://code.claude.com/docs/zh-TW/hooks.md#exit-code-output) 以了解退出代碼和 [Hook input](https://code.claude.com/docs/zh-TW/hooks.md#pretooluse-input) 以了解完整的輸入架構。

系統提示告訴 subagent 拒絕寫入請求，因此 hook 是一個後備：如果 subagent 嘗試寫入，Claude Code 會阻止命令，subagent 會看到 `Blocked: Write operations not allowed. Use SELECT queries only.` 訊息。

## 後續步驟

現在您理解了 subagents，請探索這些相關功能：

* [使用外掛程式分發 subagents](https://code.claude.com/docs/zh-TW/plugins/components.md#agents) 以跨團隊或專案共享 subagents
* [以程式方式執行 Claude Code](https://code.claude.com/docs/zh-TW/headless.md) 使用 Agent SDK 進行 CI/CD 和自動化
* [使用 MCP 伺服器](https://code.claude.com/docs/zh-TW/mcp.md) 為 subagents 提供對外部工具和資料的存取

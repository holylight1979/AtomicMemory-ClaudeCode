<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts | lastmod: 2026-10-27 | section: Agent SDK / Customize behavior -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/modifying-system-prompts（官方 zh-TW，lastmod 2026-10-27）｜分類：Agent SDK › Customize behavior｜EN 摘要：Choose between the `claude_code` preset and a custom system prompt, and customize behavior with CLAUDE.md, output styles, append, or a fully custom prompt.

# 修改系統提示詞

> 在 `claude_code` 預設和自訂系統提示詞之間選擇，並使用 CLAUDE.md、輸出樣式、append 或完全自訂提示詞來自訂行為。

系統提示詞定義了 Claude 的行為、功能和回應風格。從 `claude_code` 預設開始，適用於 CLI 或類似 IDE 的編碼工具，其中人類監督並引導工作。為具有不同介面、身份或權限模型的代理編寫您自己的提示詞。

## 系統提示詞如何運作

系統提示詞是初始指令集，塑造了 Claude 在整個對話中的行為方式。Agent SDK 有三個起點：

* **最小預設**：當您在 TypeScript 中未設定 `systemPrompt` 或在 Python 中未設定 `system_prompt` 時，SDK 使用最小提示詞，涵蓋工具呼叫但省略了 `claude_code` 預設的其餘內容，包括其安全和防護指令。這與 `claude -p` 不同，後者預設使用 Claude Code 系統提示詞。如果您正在從 CLI 遷移並想要相符的行為，請設定 `claude_code` 預設。
* **`claude_code` 預設**：Claude Code CLI 使用的系統提示詞，包含工具使用指令和安全和防護指令。在 TypeScript 中設定 `systemPrompt: { type: "preset", preset: "claude_code" }`，或在 Python 中設定 `system_prompt={"type": "preset", "preset": "claude_code"}`，可選擇使用 `append` 在末尾新增您自己的指令。
* **自訂字串**：您自己撰寫的提示詞。SDK 只會傳送您提供的內容。

### 決定起點

決定因素是您的代理與 Claude Code 的相似程度：一個在儲存庫中運作的編碼代理，有人類監看串流輸出並引導工作。您的產品離該情況越遠，您就越想撰寫自己的提示詞。

| 您正在建置 | 使用 | 您會得到 |
| :- | :- | :- |
| 一個 CLI 或類似 IDE 的編碼工具，其中人類監看並引導，而 Claude Code 的預設值是您想要的 | `claude_code` 預設 | Claude Code 提示詞，包括工具指導和安全規則 |
| 相同類型的工具，加上產品特定的規則，如編碼標準、輸出格式或領域上下文 | `claude_code` 預設搭配 `append` | 上述所有內容，加上您的指令新增在預設之後。沒有任何內容被移除，所以這是風險最低的自訂 |
| 具有不同表面、身份或權限模型的代理，或非編碼代理 | 自訂提示詞字串 | 僅您撰寫的內容。您負責替換您的代理仍需要的工具指導和安全指令 |
| 一個薄型工具呼叫迴圈，沒有代理角色，您在使用者提示詞中提供所有行為 | 無 `systemPrompt` 選項 | 最小預設：工具呼叫支援，沒有其他 |

「不同於 Claude Code」通常意味著以下其中之一：

* **不同的表面**：輸出不是由觸發它的人在終端機中讀取。聊天 UI、結構化輸出消費者和非編碼自動化各自需要一個與其輸出呈現和審查方式相符的提示詞。無人值守的編碼自動化，如修復 lint 錯誤或審查差異的 CI 工作，仍然符合預設，因為工作本身是預設為其編寫的。
* **不同的身份**：代理不應將自己呈現為 Claude Code。支援機器人、資料分析助手或任何特定領域的代理需要自己的名稱、範圍和角色。
* **不同的權限模型**：代理自主運作，無需人類批准每一步，或在一組狹隘的資源上運作。Claude Code 的提示詞假設人類在迴圈中，可以存取完整的工具集。
* **非編碼任務**：Claude Code 提示詞的大部分是編碼指導。對於研究、內容或運營代理，該指導與您實際需要的指令競爭。

[比較表](#compare-the-four-approaches)顯示每種自訂方法保留的內容。

## 自訂代理程式行為

`append` 和自訂提示詞字串各自直接改變系統提示詞，輸出樣式改變 Claude Code 給 Claude 每個回應的指令。CLAUDE.md 採用不同的路徑：SDK 讀取它並將其內容作為專案上下文注入對話中，因此它與您選擇的任何系統提示詞一起塑造行為。[Skills](https://code.claude.com/docs/zh-TW/agent-sdk/skills.md)、[hooks](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md) 和 [permissions](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md) 也在系統提示詞之外塑造行為，並在各自的頁面上涵蓋。

### 專案級指令的 CLAUDE.md 檔案

CLAUDE.md 檔案為 Claude 提供持久的專案上下文和指令。SDK 將其內容注入對話中並保持系統提示詞不變，因此它們適用於任何系統提示詞配置。關於在 CLAUDE.md 中放入什麼、放在哪裡以及如何編寫有效的指令，請參閱 [何時新增到 CLAUDE.md](https://code.claude.com/docs/zh-TW/memory.md#when-to-add-to-claude-md) 和 [Claude 如何記住您的專案](https://code.claude.com/docs/zh-TW/memory.md) 的其餘部分。本節涵蓋 SDK 特定的內容：CLAUDE.md 如何載入。

當匹配的設定來源已啟用時，SDK 讀取 CLAUDE.md：`'project'` 從工作目錄載入 `CLAUDE.md` 或 `.claude/CLAUDE.md`，`'user'` 載入 `~/.claude/CLAUDE.md`。預設 `query()` 選項啟用兩個來源，因此 CLAUDE.md 會自動載入。如果您在 TypeScript 中明確設定 `settingSources` 或在 Python 中設定 `setting_sources`，請包含您需要的來源。CLAUDE.md 載入由設定來源控制，而不是由 `claude_code` 預設值控制。

#### 使用 SDK 載入 CLAUDE.md

要載入 CLAUDE.md，請設定 `settingSources` 以包含您的 CLAUDE.md 所在的級別。下面的範例載入專案級 CLAUDE.md 以及 `claude_code` 預設值，因此 Claude 同時具有編碼代理程式提示詞和您專案的約定：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const messages = [];

for await (const message of query({
  prompt: "Add a new React component for user profiles",
  options: {
    systemPrompt: {
      type: "preset",
      preset: "claude_code" // 使用 Claude Code 的系統提示詞
    },
    settingSources: ["project"] // 從專案載入 CLAUDE.md
  }
})) {
  messages.push(message);
}

// 現在 Claude 可以存取您來自 CLAUDE.md 的專案指南
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions

messages = []


async def main():
    async for message in query(
        prompt="Add a new React component for user profiles",
        options=ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",  # 使用 Claude Code 的系統提示詞
            },
            setting_sources=["project"],  # 從專案載入 CLAUDE.md
        ),
    ):
        messages.append(message)


asyncio.run(main())

# 現在 Claude 可以存取您來自 CLAUDE.md 的專案指南
```

當您執行任一範例時，SDK 會在 Claude 工作時串流訊息：系統初始化訊息、助手訊息、攜帶工具結果的使用者訊息，以及包含會話結果的最終結果訊息。

CLAUDE.md 在專案的所有會話中持續存在，通過 git 與您的團隊共享，並自動發現而無需程式碼變更。如果您傳遞空的 `settingSources` 陣列，則不會載入。

### 輸出樣式用於持久配置

輸出樣式是修改 Claude 角色、語調和輸出格式的已儲存指令集。它們儲存為 markdown 檔案，可以在會話和專案中重複使用。

#### 建立輸出樣式

輸出樣式是一個 markdown 檔案，其 [frontmatter](https://code.claude.com/docs/zh-TW/output-styles.md#frontmatter) 中有中繼資料，後面跟著提示詞內容。將其儲存到 `~/.claude/output-styles/` 以獲得在每個專案中可用的使用者級樣式，或儲存到您的儲存庫中的 `.claude/output-styles/` 以獲得可以提交並與您的團隊共享的專案級樣式。

自訂輸出風格會省略 `claude_code` 預設值的軟體工程指令，並使用您自己的指令。要保留它們並在其上分層您的指令，請在 frontmatter 中設定 `keep-coding-instructions: true`。這些指令僅存在於 Claude Code 的完整系統提示詞中，因此該設定在使用較短系統提示詞的工作階段中無效；將 [`CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT`](https://code.claude.com/docs/zh-TW/env-vars#variables) 設定為 `0` 即可在任何模型上選用完整提示詞。當您的 agent 仍在進行軟體工程工作時保留它們。當您完全替換角色時省略它們。

下面的範例定義了程式碼審查角色，該角色保留編碼指令，因為審查程式碼仍然受益於 Claude Code 的安全性和程式碼品質指導。將其儲存為 `~/.claude/output-styles/code-reviewer.md` 以在專案中提供：

```markdown ~/.claude/output-styles/code-reviewer.md theme={null}
---
name: Code Reviewer
description: Thorough code review assistant
keep-coding-instructions: true
---

You are an expert code reviewer.

For every code submission:
1. Check for bugs and security issues
2. Evaluate performance
3. Suggest improvements
4. Rate code quality (1-10)
```

#### 啟用輸出樣式

建立後，通過以下方式啟用輸出樣式：

* **CLI**：執行 `/output-style <style>`，例如 `/output-style concise`，或執行 `/config` 並選擇一個。`/output-style` 命令需要 Claude Code v2.1.269 或更新版本。
* **設定**：在 `.claude/settings.local.json` 中設定 `outputStyle`
* **TypeScript SDK**：在傳遞給 `query()` 的內聯 `settings` 物件內設定 `outputStyle`，或將 `settings` 指向設定該值的設定檔。`outputStyle` 不是頂級 `Options` 欄位：

  ```typescript theme={null}
  const options = { settings: { outputStyle: "Explanatory" } };
  ```

在 Python SDK 中，通過 `settings` 選項設定 `outputStyle`，該選項接受 JSON 字串（例如 `'{"outputStyle": "Explanatory"}'`）或設定該值的設定檔的路徑。

**SDK 使用者注意：** 當您在選項中包含 `settingSources: ['user']` 或 `settingSources: ['project']`（TypeScript）/ `setting_sources=["user"]` 或 `setting_sources=["project"]`（Python）時，輸出樣式會被載入。

### 附加到 `claude_code` 預設值

您可以使用 Claude Code 預設值搭配 `append` 屬性來新增自訂指令，同時保留所有內建功能。

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const messages = [];

for await (const message of query({
  prompt: "Help me write a Python function to calculate fibonacci numbers",
  options: {
    systemPrompt: {
      type: "preset",
      preset: "claude_code",
      append: "Always include detailed docstrings and type hints in Python code."
    }
  }
})) {
  messages.push(message);
  if (message.type === "assistant") {
    console.log(message.message.content);
  }
}
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage

messages = []


async def main():
    async for message in query(
        prompt="Help me write a Python function to calculate fibonacci numbers",
        options=ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": "Always include detailed docstrings and type hints in Python code.",
            }
        ),
    ):
        messages.append(message)
        if isinstance(message, AssistantMessage):
            print(message.content)


asyncio.run(main())
```

#### 改進跨使用者和機器的提示詞快取

預設情況下，使用相同 `claude_code` 預設值和 `append` 文字的兩個會話仍然無法共享提示詞快取項目，當它們的自動記憶位置不同時。預設值在您的 `append` 文字之前在系統提示詞中嵌入該位置。該位置預設為 `~/.claude/projects/` 下的絕對路徑，以儲存庫在磁碟上的路徑命名，因此在使用者、機器和簽出之間不同。

CLAUDE.md 內容和環境詳細資訊（例如工作目錄、平台、shell 和 OS 版本）不會影響系統提示詞快取，因為 Claude Code 在對話中而不是系統提示詞中傳遞它們。

要使系統提示詞在會話中相同，請在 TypeScript 中設定 `excludeDynamicSections: true`，或在 Python 中設定 `"exclude_dynamic_sections": True`。每個使用者的上下文移動到第一個使用者訊息中，只在系統提示詞中保留靜態預設值和您的 `append` 文字，以便相同的配置可以在使用者和機器之間共享快取項目。

> [!NOTE]
>
> `excludeDynamicSections` 需要 `@anthropic-ai/claude-agent-sdk` v0.2.98 或更新版本，或 Python 的 `claude-agent-sdk` v0.1.58 或更新版本。僅在預設物件形式上設定它。SDK 在您傳遞自訂提示詞而不是預設值時會忽略它；要在 TypeScript SDK 中保持自訂提示詞的指令快取，請參閱 [快取自訂提示詞的靜態部分](#cache-the-static-part-of-a-custom-prompt)。

以下範例將共享 `append` 區塊與 `excludeDynamicSections` 配對，以便代理程式群隊可以重複使用相同的快取系統提示詞：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Triage the open issues in this repo",
  options: {
    systemPrompt: {
      type: "preset",
      preset: "claude_code",
      append: "You operate Acme's internal triage workflow. Label issues by component and severity.",
      excludeDynamicSections: true
    }
  }
})) {
  // ...
}
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions


async def main():
    async for message in query(
        prompt="Triage the open issues in this repo",
        options=ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": "You operate Acme's internal triage workflow. Label issues by component and severity.",
                "exclude_dynamic_sections": True,
            },
        ),
    ):
        ...


asyncio.run(main())
```

**權衡：** 移出系統提示詞的文字仍然會到達 Claude，但在使用者訊息中。該文字至少是自動記憶目錄的位置，通常是整個自動記憶部分。使用者訊息中的指令比系統提示詞中的相同文字的權重略低，因此 Claude 可能會較少一致地遵循其自動記憶指導。當跨會話快取重複使用比最大化權威環境上下文更重要時，請啟用此選項。

對於非互動式 CLI 模式中的等效旗標，請參閱 [`--exclude-dynamic-system-prompt-sections`](https://code.claude.com/docs/zh-TW/cli-reference)。

### 自訂系統提示詞

您可以提供自訂字串作為 `systemPrompt` 以完全用您自己的指令替換預設值。

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const customPrompt = `You are a Python coding specialist.
Follow these guidelines:
- Write clean, well-documented code
- Use type hints for all functions
- Include comprehensive docstrings
- Prefer functional programming patterns when appropriate
- Always explain your code choices`;

const messages = [];

for await (const message of query({
  prompt: "Create a data processing pipeline",
  options: {
    systemPrompt: customPrompt
  }
})) {
  messages.push(message);
  if (message.type === "assistant") {
    console.log(message.message.content);
  }
}
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage

custom_prompt = """You are a Python coding specialist.
Follow these guidelines:
- Write clean, well-documented code
- Use type hints for all functions
- Include comprehensive docstrings
- Prefer functional programming patterns when appropriate
- Always explain your code choices"""

messages = []


async def main():
    async for message in query(
        prompt="Create a data processing pipeline",
        options=ClaudeAgentOptions(system_prompt=custom_prompt),
    ):
        messages.append(message)
        if isinstance(message, AssistantMessage):
            print(message.content)


asyncio.run(main())
```

在 Python 中，使用 `system_prompt={"type": "file", "path": "..."}` 而不是將其作為字串傳遞，從檔案載入大型自訂提示詞。Python SDK 將字串提示詞作為一個命令列引數傳遞給 CLI 子程序，因此超過 OS 引數長度限制的提示詞在任何 API 請求發送之前在程序生成時失敗。在 Linux 上，錯誤是 `Argument list too long`。請參閱 [`SystemPromptFile`](https://code.claude.com/docs/zh-TW/agent-sdk/python#systempromptfile) 以了解平台閾值和 Windows 行為。

#### 快取自訂提示詞的靜態部分

在 TypeScript SDK 中，您可以將自訂提示詞作為字串陣列而不是一個字串傳遞，在靜態部分和其餘部分之間使用 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 標記。當您的提示詞結合每個請求上相同的指令與每個請求變更的上下文（例如代理程式正在處理的客戶或票證）時，請使用此方法。當您將兩個部分作為一個字串傳遞時，對每個請求部分的變更會改變整個系統提示詞，因此靜態指令也會錯過快取。此形式在 Python SDK 中不可用；[`ClaudeAgentOptions`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudeagentoptions) 列出 `system_prompt` 接受的形式。

> [!NOTE]
>
> SDK 僅在直接呼叫 Claude API 或在 [Claude Platform on AWS](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md) 上執行時分割提示詞。在所有其他配置中，例如 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 或 [LLM 閘道](https://code.claude.com/docs/zh-TW/llm-gateway-connect.md)，以及每當您設定 [`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`](https://code.claude.com/docs/zh-TW/llm-gateway-protocol#disable-pre-release-capabilities) 時，SDK 會將整個提示詞作為一個區塊發送，與傳遞一個字串相同。

要分割提示詞，請從 `@anthropic-ai/claude-agent-sdk` 匯入 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 並將其作為兩個部分之間的自己的陣列元素傳遞。SDK 將標記之前的字串作為一個文字區塊發送，將標記之後的字串作為第二個區塊發送，每個都有自己的快取斷點。在下面的範例中，支援代理程式從檔案載入其分類指令，並在每個請求上接收一張票證的詳細資訊，因此指令保持快取而票證詳細資訊變更：

```typescript TypeScript theme={null}
import { readFile } from "node:fs/promises";
import { query, SYSTEM_PROMPT_DYNAMIC_BOUNDARY } from "@anthropic-ai/claude-agent-sdk";

// 在每個請求上相同
const instructions = await readFile("triage-instructions.md", "utf8");
// 在每個請求上不同
const ticketContext = "Customer plan: Enterprise. Other open tickets from this customer: 3.";

for await (const message of query({
  prompt: "Triage ticket 4821",
  options: {
    systemPrompt: [instructions, SYSTEM_PROMPT_DYNAMIC_BOUNDARY, ticketContext]
  }
})) {
  // ...
}
```

[追蹤快取令牌](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md#track-cache-tokens) 描述每個結果訊息上的 `cache_creation_input_tokens` 和 `cache_read_input_tokens` 欄位。

SDK 從陣列組合區塊如下：

* SDK 在標記的每一側的字串之間用空行連接它們並移除標記本身，因此標記文字不會到達 Claude。
* 如果您多次包含標記，第一個是分割，SDK 移除其他的。
* 如果您省略標記，SDK 將所有字串連接到一個區塊中，與傳遞一個字串相同。

使用 CLI 的 [`--system-prompt` 或 `--system-prompt-file` 旗標](https://code.claude.com/docs/zh-TW/cli-reference#system-prompt-flags)，提示詞是一個字串，因此沒有陣列來攜帶標記。在靜態和每個請求部分之間改為包含僅包含 `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` 的一行。Claude Code 將提示詞在第一個這樣的行分割成相同的兩個區塊並移除該行。需要 Claude Code v2.1.275 或更新版本。

在 SDK 中，優先使用陣列形式，它不帶標記行攜帶邊界。

### 變更現有會話的提示詞

預設情況下，如果您在使用 `resume` 或 `continue` 返回會話時傳遞不同的 `append` 或自訂提示詞，Claude 在下一個回合中看不到它。Claude Code 在會話的第一個請求時記錄系統提示詞，並在會話被壓縮之前重複使用該記錄。新文字在壓縮後或在新會話中生效。

#### 在會話中更新 Claude 的指令

如果您在系統提示詞中放入的指令需要在會話執行時變更，例如因為您的使用者將代理程式切換到唯讀模式或在您的應用程式中編輯其配置，請在對話中發送新指令，而不是變更 `systemPrompt`：

* **在您的下一個訊息中**：在您發送的下一個使用者訊息中包含新指令。
* **從 hook**：從 `UserPromptSubmit` 或 `PostToolUse` [hook 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md#outputs) 傳回 [`additionalContext`](https://code.claude.com/docs/zh-TW/hooks#add-context-for-claude)，寫成事實陳述，例如「工作區現在是唯讀的」。SDK 在 hook 觸發的位置將文字插入對話中，因此記錄的提示詞保持不變。

#### 在您迭代措辭時關閉記錄

當您迭代提示詞措辭並希望每個編輯都到達您恢復的會話時，在系統提示詞的物件形式上設定 `snapshot` 為 false。Claude Code 然後在每個請求上重建提示詞。該欄位在 TypeScript 中的 [`systemPrompt`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 的預設值和自訂形式上可用，在 Python 中的 [`system_prompt`](https://code.claude.com/docs/zh-TW/agent-sdk/python#systempromptpreset) 上可用，並需要 `@anthropic-ai/claude-agent-sdk` v0.3.257 或更新版本，或 `claude-agent-sdk` v0.2.153 或更新版本。

在生產環境中保持記錄開啟。關閉記錄時，恢復的會話上的不同 `append` 或自訂提示詞在下一個回合中到達 Claude，該請求無法重複使用會話的 [提示詞快取](https://code.claude.com/docs/zh-TW/prompt-caching.md#how-the-cache-is-organized)。在 API 強制執行 [保留思考](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking) 的地方，Claude 也會失去其早期回合的思考。

在 [雲端會話](https://code.claude.com/docs/zh-TW/cloud-environments.md) 之外，如果您通過 `extraArgs` 傳遞 `--bare` 或設定 `CLAUDE_CODE_SIMPLE=1` 在 [裸模式](https://code.claude.com/docs/zh-TW/headless.md#start-faster-with-bare-mode) 中啟動 Claude Code，記錄保持關閉，除非您設定 `snapshot: true`。

預設情況下記錄 `append` 或自訂提示詞需要 Claude Code v2.1.265 或更新版本，TypeScript Agent SDK 從 v0.3.265 開始捆綁，Python Agent SDK 從 v0.2.153 開始捆綁。在 Claude Code v2.1.268 之前，不 [擷取功能旗標](https://code.claude.com/docs/zh-TW/env-vars.md#features-that-need-feature-flag-fetching) 的會話，包括 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上的會話，在每個請求上重建提示詞，`snapshot` 無效。

## Claude Code 在系統提示之外新增的上下文

系統提醒是 Claude Code 在工作階段期間新增到對話中的訊息，用於為 Claude 提供上下文，例如您的 CLAUDE.md 檔案內容或檔案在磁碟上已變更的備註。Claude Code 在對話中傳送這些訊息，而不是在系統提示詞中，因此無論您使用 `claude_code` 預設值還是傳遞您自己的字串作為 `systemPrompt`，大多數提醒都會到達 Claude。

本節涵蓋[最可能改變您代理程式行為的提醒](#reminders-claude-code-adds-to-the-conversation)、如何[關閉您的代理程式取代的提醒](#turn-off-the-context-your-agent-replaces)，以及如何[查看 Claude 在特定請求中收到的內容](#see-what-claude-received)。

### Claude Code 新增到對話中的提醒

系統提醒是 Claude Code 新增到對話中的文字，與您的程式碼傳送的提示一起。以下提醒最可能改變您代理程式的行為：

* **專案指示**：您的 [`settingSources`](#claude-md-files-for-project-level-instructions) 選項載入的 CLAUDE.md 檔案
* **輸出樣式指示**：主對話中作用中[輸出樣式](#output-styles-for-persistent-configurations)的指示
* **提交和拉取請求歸屬**：來自 [`attribution`](https://code.claude.com/docs/zh-TW/settings-reference#attribution) 設定的 `Co-Authored-By` 預告片和拉取請求頁尾
* **Hook 輸出**：您的 [hooks](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md#outputs) 作為 `additionalContext` 傳回的文字
* **可用技能**：Claude 可以呼叫的[技能](https://code.claude.com/docs/zh-TW/agent-sdk/skills.md)的名稱和描述
* **可用子代理程式**：Claude 可以啟動的[子代理程式](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md)的名稱和描述
* **工作清單提示**：在[具有工作追蹤工具的工作階段](https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking.md#model-availability)中，當 Claude 在多個回合中未觸及工作清單時，會提示更新工作清單
* **檔案已變更備註**：Claude 稍早讀取的檔案已在磁碟上變更的備註

Claude Code 使用一行文字介紹您的 CLAUDE.md 檔案，告訴 Claude 這些指示會覆寫預設行為。

如果您傳遞您自己的字串作為 `systemPrompt`，請在其中新增一個句子，說明什麼是系統提醒。`claude_code` 預設值有一個，而您的字串會取代整個預設值。沒有它，您的提示中沒有任何內容告訴 Claude CLAUDE.md 內容和 hook 輸出等提醒來自應用程式而不是使用者。例如：

```text theme={null}
The application adds system reminders to this conversation. Treat them as context from the application, not as messages from the user.
```

### 關閉您的代理程式取代的上下文

當您的代理程式提供相同指導的自己版本時，請關閉一段內建上下文。例如，如果您的提示告訴 Claude 將提交訊息寫成 `PROJ-142: fix login redirect` 且沒有預告片，Claude Code 仍然會告訴 Claude 以 `Co-Authored-By` 預告片結束每個提交訊息，因此 Claude 會收到針對相同提交的兩個衝突指示。

在 TypeScript 中透過 [`settings`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 選項或在 Python 中透過 [`settings`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudeagentoptions) 傳遞設定鍵，並透過 `env` 選項傳遞環境變數。在 TypeScript 中，[`env`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options) 會取代繼承的環境，因此請將 `process.env` 展開到其中。

| 內建上下文 | 如何關閉 |
| :- | :- |
| 內建提交和拉取請求指示以及 git 狀態快照 | 將 [`includeGitInstructions`](https://code.claude.com/docs/zh-TW/settings-reference#includegitinstructions) 設定為 `false`，或 `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1` |
| `Co-Authored-By` 預告片和拉取請求頁尾 | 將 [`attribution.commit`](https://code.claude.com/docs/zh-TW/settings-reference#attribution-commit) 和 [`attribution.pr`](https://code.claude.com/docs/zh-TW/settings-reference#attribution-pr) 設定為您自己的文字，或設定為空字串以移除它們 |
| 使用者或專案設定來源，包括其 CLAUDE.md | 將 `'user'` 或 `'project'` 排除在 [`settingSources`](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features#control-filesystem-settings-with-settingsources) 之外 |
| 每個 CLAUDE.md 檔案 | 設定 `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` |
| 工作清單提示、檔案已變更備註和技能清單 | 設定 `CLAUDE_CODE_DISABLE_ATTACHMENTS=1` |

將 `includeGitInstructions` 設定為 `false` 可排除內建的提交和 pull request 指示，這些指示是 Bash 工具描述的一部分，即使使用自訂 `systemPrompt` 也會到達 Claude。不過，在使用最小預設值、自訂 `systemPrompt`，或具有自己提示詞的自訂主執行緒 agent 時，工作階段開始時本來就不含 git 狀態快照。

* 如果您設定 `CLAUDE_CODE_DISABLE_ATTACHMENTS`，Claude Code 也會將 `@` 檔案提及作為純文字傳送，而不是將其展開為檔案內容。可用 subagent 清單和背景任務通知仍然會到達。
* 若只要停止展開 `@` 檔案提及，請改為設定 [`CLAUDE_CODE_DISABLE_FILE_MENTIONS=1`](https://code.claude.com/docs/zh-TW/env-vars#variables)，需使用 Claude Code v2.1.299 或更新版本。Claude 接著會收到所提及的路徑，以及一則要求使用其檔案工具讀取這些路徑的備註，而您的 `PreToolUse` hook 會將每次檔案讀取視為一次工具呼叫。

以下範例適用於在 `append` 中攜帶自己提交規則的代理程式。它將兩個 `attribution` 鍵設定為空字串以移除預告片和頁尾，並關閉 `includeGitInstructions`，以便 Claude Code 自己的提交工作流程指示不會與您的指示競爭：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Commit the staged changes for ticket PROJ-142",
  options: {
    systemPrompt: {
      type: "preset",
      preset: "claude_code",
      append: "Write commit messages as: <ticket id>: <summary>. Add no trailers."
    },
    settings: {
      includeGitInstructions: false,
      attribution: { commit: "", pr: "" }
    },
    allowedTools: ["Bash(git *)"]
  }
})) {
  if (message.type === "result") console.log(message.subtype);
}
```

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions


async def main():
    async for message in query(
        prompt="Commit the staged changes for ticket PROJ-142",
        options=ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": "Write commit messages as: <ticket id>: <summary>. Add no trailers.",
            },
            settings='{"includeGitInstructions": false, "attribution": {"commit": "", "pr": ""}}',
            allowed_tools=["Bash(git *)"],
        ),
    ):
        print(message)


asyncio.run(main())
```

若要確認變更，請在具有暫存變更的儲存庫中執行範例，並使用 `git log -1` 檢查新提交。訊息結尾沒有 `Co-Authored-By` 預告片。

### 查看 Claude 收到的內容

SDK 訊息串流不包括系統提醒，因此讀取您的程式碼收到的訊息不會向您顯示 Claude 看到的內容。若要查看它們，請記錄 Claude Code 傳送的請求：

* **原始請求記錄**：將 [`OTEL_LOG_RAW_API_BODIES`](https://code.claude.com/docs/zh-TW/monitoring-usage#api-request-body-event) 設定為 `file:<dir>`。Claude Code 會將每個請求本體寫入該目錄。
* **您控制的閘道**：將 [`ANTHROPIC_BASE_URL`](https://code.claude.com/docs/zh-TW/llm-gateway) 指向記錄請求本體的代理。

在記錄的請求中，查看 `messages` 陣列。提醒會出現在包裝在 `<system-reminder>` 標籤中的使用者訊息內，或在某些模型上，作為具有 `system` 角色的單獨訊息。

## 比較四種方法

四種自訂方法在位置、共享方式和從 `claude_code` 預設保留的內容方面有所不同。

| 功能 | CLAUDE.md | 輸出樣式 | `systemPrompt` 附加 | 自訂 `systemPrompt` |
| - | - | - | - | - |
| **持久性** | 每個專案檔案 | 儲存為檔案 | 僅限會話 | 僅限會話 |
| **可重複使用性** | 每個專案 | 跨專案 | 程式碼重複 | 程式碼重複 |
| **管理** | 在檔案系統上 | CLI + 檔案 | 在程式碼中 | 在程式碼中 |
| **預設工具** | 保留 | 保留 | 保留 | 遺失（除非包含） |
| **內建安全** | 維持 | 維持 | 維持 | 必須新增 |
| **自訂程度** | 僅新增 | 新增；可省略程式設計指示 | 僅新增 | 完全控制 |
| **版本控制** | 與專案一起 | 是 | 與程式碼一起 | 與程式碼一起 |
| **範圍** | 專案特定 | 使用者或專案 | 程式碼會話 | 程式碼會話 |

「附加」是指在 TypeScript 中使用 `systemPrompt: { type: "preset", preset: "claude_code", append: "..." }`，或在 Python 中使用 `system_prompt={"type": "preset", "preset": "claude_code", "append": "..."}`。CLAUDE.md 不會變更系統提示本身：SDK 會將其內容作為專案上下文注入到對話中。

## 組合方法

這些方法可以組合使用。持久輸出樣式或 CLAUDE.md 設定長期行為，而 `append` 在不觸及已儲存設定的情況下，在頂層疊加工作階段特定的指令。

### 將輸出樣式與工作階段特定的新增項目組合

下面的範例假設已經啟用 Code Reviewer 輸出樣式。`append` 區塊在角色上疊加工作階段特定的焦點領域，因此單一審查工作階段可以優先考慮 OAuth 和權杖儲存，而無需變更已儲存的輸出樣式：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

// Assuming "Code Reviewer" output style is active (via /config or settings)
// Add session-specific focus areas
const messages = [];

for await (const message of query({
  prompt: "Review this authentication module",
  options: {
    systemPrompt: {
      type: "preset",
      preset: "claude_code",
      append: `
        For this review, prioritize:
        - OAuth 2.0 compliance
        - Token storage security
        - Session management
      `
    }
  }
})) {
  messages.push(message);
}
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions

# Assuming "Code Reviewer" output style is active (via /config or settings)
# Add session-specific focus areas
messages = []


async def main():
    async for message in query(
        prompt="Review this authentication module",
        options=ClaudeAgentOptions(
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": """
                For this review, prioritize:
                - OAuth 2.0 compliance
                - Token storage security
                - Session management
                """,
            }
        ),
    ):
        messages.append(message)


asyncio.run(main())
```

## 另請參閱

* [輸出樣式](https://code.claude.com/docs/zh-TW/output-styles.md)：為 CLI 建立、管理和分享輸出樣式，包括檔案格式和儲存位置
* [Claude 如何記住您的專案](https://code.claude.com/docs/zh-TW/memory.md)：CLAUDE.md 中應放入的內容、放置位置，以及如何撰寫有效的專案指示
* [TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md)：完整的 `Options` 類型，包括 `systemPrompt`、`settingSources` 和 `settings`
* [Python SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md)：完整的 `ClaudeAgentOptions` 類型，包括 `system_prompt` 和 `setting_sources`
* [設定](https://code.claude.com/docs/zh-TW/settings.md)：`settings.json` 參考，包括輸出樣式和其他配置的儲存位置

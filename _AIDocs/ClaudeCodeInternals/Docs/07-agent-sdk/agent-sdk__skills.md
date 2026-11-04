<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/skills | lastmod: 2026-10-23 | section: Agent SDK / Customize behavior -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/skills（官方 zh-TW，lastmod 2026-10-23）｜分類：Agent SDK › Customize behavior｜EN 摘要：Control which skills Claude can invoke in Claude Agent SDK sessions, dispatch commands by name, and author skills your sessions discover

# 使用 Skills 擴展 Agent

> 控制 Claude 在 Claude Agent SDK 會話中可以調用的 Skills，按名稱分派命令，以及編寫會話發現的 Skills

Agent Skills 使用專門功能擴展 Claude，Claude 會在相關時自動調用這些功能。Skills 被打包為 `SKILL.md` 文件，包含說明、描述和可選的支持資源。本頁面也涵蓋了 [Agent SDK 會話中的命令](#commands-in-agent-sdk-sessions)。

有關 Skills 的更多資訊，包括優勢、架構和編寫指南，請參閱 [Agent Skills 概述](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)。

## Skills 如何與 Agent SDK 搭配運作

使用 Claude Agent SDK 時，skills 具有以下特性：

* **定義為檔案系統成品**：你在自己的目錄中建立每個 skill 作為 `SKILL.md` 檔案，例如 `.claude/skills/<name>/SKILL.md`
* **從檔案系統載入**：SDK 從由 `settingSources`（TypeScript）或 `setting_sources`（Python）控制的檔案系統位置載入 skills
* **自動探索**：一旦檔案系統設定載入，SDK 會在啟動時從使用者和專案目錄探索 skill 中繼資料，並在 Claude 叫用 skill 時載入完整內容
* **由模型叫用**：Claude 根據上下文自主選擇何時使用它們
* **由使用者叫用**：你可以在提示中傳送 `/<name>` 來直接分派 skill。請參閱 [Agent SDK 工作階段中的命令](#commands-in-agent-sdk-sessions)
* **透過 `skills` 選項進行範圍設定**：探索到的 skills 預設為啟用。傳遞 skill 名稱清單、`"all"` 或 `[]` 來控制 Claude 可以叫用哪些 skills

與你可以在 [`agents` 選項](https://code.claude.com/docs/zh-TW/agent-sdk/subagents#programmatic-definition-recommended)中定義的 subagents 不同，你將 skills 建立為磁碟上的檔案。SDK 不提供用於註冊它們的程式設計 API。

> [!NOTE]
>
> Skills 透過檔案系統設定來源進行探索。使用預設 `query()` 選項時，SDK 會載入使用者和專案來源，因此 `~/.claude/skills/`、`<cwd>/.claude/skills/` 和 `.claude/skills/` 中的 skills（位於 `<cwd>` 的任何父目錄中，直到儲存庫根目錄）都可用。專案來源也涵蓋 `<dir>/.claude/skills/`（位於你透過 `additionalDirectories`（TypeScript）或 `add_dirs`（Python）傳遞的每個目錄中），因為 SDK 會將這些目錄作為 [`--add-dir`](https://code.claude.com/docs/zh-TW/skills#skills-from-additional-directories) 傳遞給 Claude Code。如果你明確設定 `settingSources`，請包含 `'project'` 以保留專案和新增目錄 skills，以及 `'user'` 以保留你的個人 skills，或使用 [`plugins` 選項](https://code.claude.com/docs/zh-TW/agent-sdk/plugins)從特定路徑載入 skills。

## 在 Agent SDK 中使用 skill

在 `query()` 上設定 `skills` 選項，以控制 Claude 在工作階段中可以叫用哪些 skill。省略時，會啟用已探索到的 skill，且 Skill 工具可用，與 CLI 的行為一致。傳入 `"all"` 可讓 Claude 叫用每個已探索到的 skill；傳入 skill 名稱清單則僅允許這些 skill；傳入 `[]` 則讓 Claude 不叫用任何 skill。

例如，若只要讓 Claude 叫用兩個指定名稱的 skill：

```python Python theme={null}
options = ClaudeAgentOptions(skills=["pdf", "docx"])
```

```typescript TypeScript theme={null}
const options = { skills: ["pdf", "docx"] };
```

### 在工作階段中設定 skill

當您設定 `skills` 時，SDK 會自動將 Skill 工具新增至 `allowedTools`。如果您也傳入明確的 `tools` 清單，請在該清單中包含 `"Skill"`，以便 Claude 可以叫用 skill。

設定完成後，Claude 會自動從檔案系統探索 skill，並在與使用者請求相關時叫用它們。

以下範例會在工作階段中啟用每個已探索到的 skill，並預先核准 skill 通常需要的工具。此範例將 `cwd` 設定為程序的目前工作目錄，因此請在一個專案內執行它，該專案的目前目錄或任何上層目錄（直到儲存庫根目錄）中須有 `.claude/skills/` 目錄：

```python Python theme={null}
import asyncio
import os

from claude_agent_sdk import query, ClaudeAgentOptions


async def main():
    options = ClaudeAgentOptions(
        cwd=os.getcwd(),  # .claude/skills/ here or in a parent directory
        setting_sources=["user", "project"],  # Load skills from filesystem
        skills="all",  # Let Claude invoke every discovered skill
        allowed_tools=["Read", "Write", "Bash"],
    )

    async for message in query(
        prompt="Help me process this PDF document", options=options
    ):
        print(message)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Help me process this PDF document",
  options: {
    cwd: process.cwd(), // .claude/skills/ here or in a parent directory
    settingSources: ["user", "project"], // Load skills from filesystem
    skills: "all", // Let Claude invoke every discovered skill
    allowedTools: ["Read", "Write", "Bash"]
  }
})) {
  console.log(message);
}
```

### 確認 skill 已載入

在串流開始不久，SDK 會產生一個子類型為 `init` 的系統訊息。檢查其 `skills` 陣列，以在 Claude 開始工作之前確認您的 skill 已載入。該陣列包含您以 `description` 或 `when_to_use` frontmatter 欄位定義的使用者可叫用 skill，以及 [Claude Code 隨附的 skill](https://code.claude.com/docs/zh-TW/skills.md#bundled-skills)。

該陣列僅列出使用者可叫用的 skill。在 frontmatter 中設有 [`user-invocable: false`](https://code.claude.com/docs/zh-TW/skills#control-who-invokes-a-skill) 的 skill 仍會載入並可供 Claude 使用，但不會出現在陣列中。無論 skill 是否在您的 `skills` 清單中，該陣列列出的 skill 都相同。

### 僅允許特定 skill

若只要讓 Claude 叫用特定 skill，請在 `skills` 清單中傳入它們的名稱：

* **您自己的 skill**：skill 的目錄名稱
* **外掛 skill**：`plugin:skill`
* **`additionalDirectories` 或 `add_dirs` 中的名稱衝突**：當這些目錄之一中的 skill 與企業、個人或專案 skill，或與較早新增之目錄中的 skill 名稱衝突時，會取得一個[加上前綴的名稱](https://code.claude.com/docs/zh-TW/skills.md#how-a-skill-gets-its-command-name)。請以該名稱列出它。若 `../api` 與 `../web` 中各有一個 `verify` skill，並依此順序新增，且沒有其他 `verify` skill，請將它們列為 `verify` 和 `web:verify`。需要 Claude Code v2.1.309 或更新版本

該清單僅接受確切的 skill 名稱。如果某個項目無法作為確切名稱使用，`query()` 會在工作階段開始前拒絕該清單。請參閱[無效的 skill 名稱錯誤](#invalid-skill-name-error)，以了解名稱規則以及各 SDK 引發的錯誤。

模型看不到未列出的 skill，Skill 工具也會拒絕它們，但它們的檔案仍保留在磁碟上，並可透過 Read 和 Bash 存取。限制清單並不會限制[依名稱分派](#dispatch-commands-by-name)。

若要讓 Claude 叫用每個已探索到的 skill，請傳入 `skills: "all"`，而非萬用字元。

## Agent SDK 工作階段中的命令

本節是 SDK 的命令文件。命令是您透過在提示中傳送 `/<name>` 來執行的任何操作。命令表面上的項目在其支援方式上有所不同：

* **內建命令**：執行編碼到 Claude Code 程序中的邏輯，例如 `/compact`
* **捆綁技能**：隨 Claude Code 一起提供的提示工件，例如 `/code-review`
* **您的技能**：您編寫的提示工件，每個都是包含 `SKILL.md` 檔案的目錄。使用者可呼叫的技能名稱會自動加入表面，因此分派您自己的 `/security-check` 和執行內建命令的方式相同
* **自訂命令檔案**：一種較舊的工件形式，具有相同的行為，位於 `.claude/commands/` 中的平面 Markdown 檔案，其檔案名稱會變成命令名稱。技能是其推薦的後繼者

根據預設，您和 Claude 都可以呼叫任何技能。您可以透過技能的[前置資料](https://code.claude.com/docs/zh-TW/skills.md#control-who-invokes-a-skill)限制任一路徑。如需命令和技能的定義，請參閱詞彙表的[命令](https://code.claude.com/docs/zh-TW/glossary.md#command)和[技能](https://code.claude.com/docs/zh-TW/glossary.md#skill)項目。請參閱[Claude Code 中的命令](https://code.claude.com/docs/zh-TW/commands.md)以了解每個內建命令，以及[使用技能擴展 Claude](https://code.claude.com/docs/zh-TW/skills.md)以了解兩種工件形式的完整指南。

### 探索可用命令

您可以透過 SDK 分派無需互動式終端機的命令。`system/init` 訊息在其 `slash_commands` 欄位中列出工作階段中可用的命令。需要互動式終端機的命令（例如 `/theme` 和 `/terminal-setup`）不會出現在清單中。在工作階段開始時存取該欄位：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Hello Claude",
  options: { maxTurns: 1 }
})) {
  if (message.type === "system" && message.subtype === "init") {
    console.log("Available commands:", message.slash_commands);
  }
}
```

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, SystemMessage


async def main():
    async for message in query(prompt="Hello Claude", options=ClaudeAgentOptions(max_turns=1)):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            print("Available commands:", message.data["slash_commands"])


asyncio.run(main())
```

列印的清單混合了內建命令、捆綁技能、您的使用者可呼叫技能和 `.claude/commands/` 檔案：

```text theme={null}
Available commands: ["clear", "compact", "context", "usage", "code-review", "verify", "security-check", ...]
```

在其前置資料中具有 [`user-invocable: false`](https://code.claude.com/docs/zh-TW/skills#control-who-invokes-a-skill) 的技能不會出現在此清單或[確認技能已載入](#confirm-skills-loaded)中的 `skills` 陣列中。設定 [MCP 伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md)的工作階段也可以公開 [MCP 提示作為命令](https://code.claude.com/docs/zh-TW/mcp.md#use-mcp-prompts-as-commands)。

### 按名稱分派命令

透過將命令包含在提示字串中來傳送命令，就像傳送一般文字一樣。分派不取決於 `skills` 選項。傳送 `/<name>` 會執行使用者可呼叫的技能，即使您的 `skills` 清單省略了它。作用於對話歷史記錄的命令（例如 `/compact`）需要先前的訊息才能使用。

一個 `/<name>` 既不符合工作階段中的命令也不符合內建 Claude Code 命令的情況不會導致查詢失敗。Claude Code 會將提示傳送給 Claude 作為一般訊息，並附上命令未執行的說明，因此查詢會花費一個模型輪次並返回 Claude 的回覆。在 v2.1.274 之前，一個不符合任何內容的 `/<name>` 會返回 `Unknown command: /<name>` 作為結果，不花費模型輪次。

一個 `/<name>` 符合在工作階段中不可用的內建 Claude Code 命令（例如 `/theme`）會返回 `/theme isn't available in this environment.` 作為結果，不花費模型輪次。

> [!NOTE]
>
> 命令可以像任何其他提示一樣達到 `maxTurns` / `max_turns` 限制，以錯誤結果而不是 `success` 結束查詢。如需錯誤結果合約，請參閱[處理結果](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#handle-the-result)。如果您的命令可能達到限制，請在 TypeScript 中用 `try`/`catch` 或在 Python 中用 `try`/`except` 包裝迴圈，如[單一訊息輸入](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md#single-message-input)中所示，或設定 `maxTurns` 足夠高以完成工作。

### 使用 `/compact` 壓縮歷史記錄

`/compact` 命令透過總結較舊的訊息同時保留重要內容來減少對話歷史記錄的大小。壓縮需要現有的對話，其中有足夠的先前訊息要總結。此範例首先有一個對話，然後壓縮它並讀取報告結果的 `compact_boundary` 系統訊息：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

// Compaction needs existing history, so have a conversation first
try {
  for await (const message of query({
    prompt: "Explain what this project does",
    options: { maxTurns: 2 }
  })) {
    if (message.type === "result" && message.subtype === "success") {
      console.log(message.result);
    }
  }
} catch (error) {
  // A single-shot query() throws after yielding an error result,
  // so the follow-up query below still runs.
  console.error(`Session ended with an error: ${error}`);
}

// Compact the same conversation
for await (const message of query({
  prompt: "/compact",
  options: { continue: true, maxTurns: 1 }
})) {
  if (message.type === "system" && message.subtype === "compact_boundary") {
    console.log("Compaction completed");
    console.log("Pre-compaction tokens:", message.compact_metadata.pre_tokens);
    console.log("Trigger:", message.compact_metadata.trigger);
    // Example output:
    // Compaction completed
    // Pre-compaction tokens: 1842
    // Trigger: manual
  }
}
```

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage, SystemMessage


async def main():
    # Compaction needs existing history, so have a conversation first
    try:
        async for message in query(
            prompt="Explain what this project does",
            options=ClaudeAgentOptions(max_turns=2),
        ):
            if isinstance(message, ResultMessage) and message.subtype == "success":
                print(message.result)
    except Exception as error:
        # A single-shot query() raises after yielding an error result,
        # so the follow-up query below still runs.
        print(f"Session ended with an error: {error}")

    # Compact the same conversation
    async for message in query(
        prompt="/compact",
        options=ClaudeAgentOptions(continue_conversation=True, max_turns=1),
    ):
        if isinstance(message, SystemMessage) and message.subtype == "compact_boundary":
            print("Compaction completed")
            print("Pre-compaction tokens:", message.data["compact_metadata"]["pre_tokens"])
            print("Trigger:", message.data["compact_metadata"]["trigger"])
            # Example output:
            # Compaction completed
            # Pre-compaction tokens: 1842
            # Trigger: manual


asyncio.run(main())
```

> [!NOTE]
>
> `compact_boundary` 訊息只在壓縮執行時到達。當繼續的工作階段有訊息但 `/compact` 無法總結任何內容時，執行仍以 `success` 結果結束，而不是錯誤，且沒有 `compact_boundary` 訊息到達。結果文字會帶有原因，例如當工作階段持有提示但尚未收到 Claude 的回覆時的 `Not enough messages to compact.`。全新的單一查詢 `query()` 呼叫以空內容開始，因此請在具有先前輪次的工作階段中使用此模式，例如在[串流輸入模式](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)中或恢復工作階段時。

### 使用 `/clear` 重設內容

`/clear` 命令將對話重設為空內容，因此後續提示以沒有先前對話歷史記錄開始。先前的對話保留在磁碟上。您可以透過將其工作階段 ID 傳遞給[`resume` 選項](https://code.claude.com/docs/zh-TW/agent-sdk/sessions#resume-by-id)來返回該對話。

`/clear` 在[串流輸入模式](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)中很有用，您可以在單一連線上傳送多個提示。對於單一查詢 `query()` 呼叫，每個呼叫已經以空內容開始，因此傳送 `/clear` 沒有實際效果。改為啟動新的 `query()`。

## 創建 Skills

將每個 Skill 創建為包含具有 YAML frontmatter 和 Markdown 內容的 `SKILL.md` 文件的目錄。`description` 欄位確定 Claude 何時調用您的 Skill。

**示例目錄結構**：

```text theme={null}
.claude/skills/security-check/
└── SKILL.md
```

### 選擇發現級別

在兩個最常見的 [發現級別](https://code.claude.com/docs/zh-TW/skills.md#where-skills-live) 中保存 Skills：

* **項目 Skills**：`.claude/skills/`，僅在當前項目中可用
* **個人 Skills**：`~/.claude/skills/`，在所有項目中可用

如果您在 `.claude/commands/` 中有現有的自定義命令文件，它們會繼續工作。`.claude/commands/deploy.md` 中的命令文件創建 `/deploy` 並以與 `.claude/skills/deploy/SKILL.md` 中的 Skill 相同的方式工作。如果命令文件和 Skill 共享名稱，請參閱 [解決共享名稱的 Skills](https://code.claude.com/docs/zh-TW/skills.md#resolve-skills-that-share-a-name) 以了解哪一個運行。SDK 從與 Skills 相同的兩個範圍加載 `.claude/commands/` 和 `~/.claude/commands/` 文件。請參閱 [使用 Skills 擴展 Claude](https://code.claude.com/docs/zh-TW/skills.md) 以了解兩種工件形式的完整指南。

### 創建並分派您的第一個 Skill

要查看完整流程，請創建 `.claude/skills/security-check/SKILL.md`：

```markdown theme={null}
---
name: security-check
description: Run a security vulnerability scan
---

Analyze the codebase for security vulnerabilities including:
- SQL injection risks
- XSS vulnerabilities
- Exposed credentials
- Insecure configurations
```

文件存在後，Skill 可通過 SDK 使用。Claude 在請求與其描述匹配時調用它，您可以直接分派它：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "/security-check",
  options: { maxTurns: 10 }
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log(message.result);
  }
}
```

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage


async def main():
    async for message in query(
        prompt="/security-check", options=ClaudeAgentOptions(max_turns=10)
    ):
        if isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


asyncio.run(main())
```

成功的運行以 `success` 結果結束，其文本包含掃描發現。針對具有植入問題的小型 Express 應用程式，結果文本開始於：

```text theme={null}
**Security scan of `app.js` — 4 findings (most severe first):**

1. **SQL Injection** (line 8) — `req.query.name` is concatenated directly into the SQL string. Trivially exploitable (`' OR '1'='1`, `'; DROP TABLE users;--`). **Fix:** use parameterized queries, e.g. `db.query("SELECT * FROM users WHERE name = ?", [req.query.name], cb)`.
...
```

Skill 的名稱也出現在初始化消息的 `slash_commands` 陣列中。

> [!NOTE]
>
> Claude Code 包括捆綁的 `code-review` 和 `verify` Skills。如果您以其中之一命名 `.claude/commands/` 文件，例如 `.claude/commands/code-review.md`，該文件的命令會遮蔽捆綁的 Skill，`slash_commands` 列出名稱一次。

## 為 Skills 預先批准工具

> [!NOTE]
>
> 在 SDK 工作階段中，您可以透過 skill 的 [`allowed-tools`](https://code.claude.com/docs/zh-TW/skills#pre-approve-tools-for-a-skill) frontmatter，或透過查詢設定中的 `allowedTools` 選項（Python 中為 `allowed_tools`），為專案或個人 skill 預先核准工具。如果您的組織在受管設定中設定了 [`allowManagedPermissionRulesOnly`](https://code.claude.com/docs/zh-TW/settings-reference#allowmanagedpermissionrulesonly)，Claude Code 會忽略這兩者。[從 claude.ai 同步](https://code.claude.com/docs/zh-TW/skills.md#how-claude-code-handles-the-frontmatter-of-a-synced-skill)的 skill 遵循其自身的 frontmatter 規則。

Skills 使用會話的工具運行。下面的示例使用 `allowedTools`（Python 中的 `allowed_tools`）預先批准 `Read`、`Grep` 和 `Glob`，因此 Claude 可以在運行 [security-check Skill](#create-and-dispatch-your-first-skill) 時檢查文件，而無需停止以獲得批准：

```python Python theme={null}
import asyncio

from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(
    setting_sources=["user", "project"],  # Load skills from filesystem
    skills="all",
    allowed_tools=["Read", "Grep", "Glob"],
)


async def main():
    async for message in query(prompt="Check this project for security issues", options=options):
        print(message)


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Check this project for security issues",
  options: {
    settingSources: ["user", "project"], // Load skills from filesystem
    skills: "all",
    allowedTools: ["Read", "Grep", "Glob"]
  }
})) {
  console.log(message);
}
```

在流中，Skill 調用顯示為 Skill 工具使用，後跟對項目文件的 Read 調用。運行以 `success` 結果結束，其文本包含發現。

該列表預先批准命名的工具，而不是限制其他工具。有關完整的權限流程，包括權限模式和 `canUseTool` 回調，請參閱 [權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)。

## 疑難排解

### 找不到 Skills

**檢查 settingSources 設定**：SDK 透過 `user` 和 `project` 設定來源探索 skills。如果您明確設定 `settingSources`/`setting_sources` 並省略這些來源，SDK 不會載入 skills：

```python Python theme={null}
# Skills 未載入：setting_sources 排除了 user 和 project
options = ClaudeAgentOptions(setting_sources=[], skills="all")

# Skills 已載入：user 和 project 來源已包含
options = ClaudeAgentOptions(
    setting_sources=["user", "project"],
    skills="all",
)
```

```typescript TypeScript theme={null}
// Skills 未載入：settingSources 排除了 user 和 project
const optionsWithoutSkills = {
  settingSources: [],
  skills: "all"
};

// Skills 已載入：user 和 project 來源已包含
const optionsWithSkills = {
  settingSources: ["user", "project"],
  skills: "all"
};
```

如需了解每個來源載入的 skill 目錄，請參閱[檔案系統來源表](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#control-filesystem-settings-with-settingsources)。如需更多關於 `settingSources`/`setting_sources` 的詳細資訊，請參閱 [TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#settingsource)或 [Python SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#settingsource)。

**檢查工作目錄**：SDK 從 `cwd` 選項中的 `.claude/skills/` 以及每個父目錄（直到儲存庫根目錄）載入 skills。確保 `cwd` 指向包含 `.claude/skills/` 的目錄或其下方目錄，且在同一個儲存庫內：

```python Python theme={null}
# 確保您的 cwd 指向包含 .claude/skills/ 的目錄
options = ClaudeAgentOptions(
    cwd="/path/to/project",  # .claude/skills/ 在此或在父目錄中
    setting_sources=["user", "project"],  # 從這些來源載入 skills
    skills="all",
)
```

```typescript TypeScript theme={null}
// 確保您的 cwd 指向包含 .claude/skills/ 的目錄
const options = {
  cwd: "/path/to/project", // .claude/skills/ 在此或在父目錄中
  settingSources: ["user", "project"], // 從這些來源載入 skills
  skills: "all"
};
```

請參閱[使用 Agent SDK 的 Skills](#use-skills-with-the-agent-sdk) 以了解完整的模式。

**驗證檔案系統位置**：

```bash theme={null}
# 檢查專案 skills
ls .claude/skills/*/SKILL.md

# 檢查個人 skills
ls ~/.claude/skills/*/SKILL.md
```

### Skill 未被使用

**檢查 `skills` 選項**：如果您傳遞了 `skills` 清單，請確認 skill 的名稱已包含在內。當 Claude 嘗試叫用未列出的 skill 時，Skill 工具會傳回 `Skill <name> is not in this session's skills allowlist`。將名稱新增到您的清單中，或透過在提示中傳送 `/<name>` 直接分派 skill，這樣無需列出即可運作。

**檢查描述**：確保它具體且包含相關關鍵字。請參閱 [Agent Skills 最佳實踐](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#writing-effective-descriptions)以取得有關撰寫有效描述的指導。

### 無效的 skill 名稱錯誤

當您 `skills` 清單中的名稱無法作為確切的 skill 名稱時，`query()` 會在啟動 Claude Code 程序之前拒絕該清單。觸發拒絕的名稱包括：

* 空名稱
* 包含括號、逗號或控制字元的名稱
* 用空白字元填充的名稱
* 萬用字元形式，例如裸露的 `*` 或 `:*` 後綴

每個 SDK 以不同的方式呈現拒絕：

> [tab] TypeScript
>
> TypeScript SDK 會擲出 `Error`，說明項目違反的規則。例如，`skills: ["docs:*"]` 會擲出：
>
> ```text theme={null}
> Invalid skill name "docs:*": wildcard-suffix names are not allowed; list each skill by its exact name.
> ```
>
> 空名稱會報告 `Skill names must be non-empty strings.`
>
> 在 TypeScript Agent SDK 0.3.221 之前，SDK 未執行此檢查。

> [tab] Python
>
> Python SDK 會引發 `ValueError`，說明項目違反的規則。例如，`skills=["docs:*"]` 會引發：
>
> ```text theme={null}
> ValueError: Invalid skill name 'docs:*': wildcard-suffix names are not allowed; list each skill by its exact name.
> ```
>
> 空名稱會報告 `Skill names must be non-empty strings`。
>
> 在 Python Agent SDK 0.2.129 之前，SDK 未執行此檢查。

### 其他疑難排解

如需一般 skills 疑難排解，例如 YAML 語法錯誤和偵錯，請參閱 [Claude Code skills 疑難排解部分](https://code.claude.com/docs/zh-TW/skills.md#troubleshooting)。

## 後續步驟

[Claude Code Skills 指南](https://code.claude.com/docs/zh-TW/skills.md) 涵蓋了深入的編寫。其指導適用於 SDK 會話。從這些部分開始：

* [Frontmatter 參考](https://code.claude.com/docs/zh-TW/skills.md#frontmatter-reference)：每個支持的欄位
* [將引數傳遞給 skills](https://code.claude.com/docs/zh-TW/skills.md#pass-arguments-to-skills)：`$ARGUMENTS`、`$0` 和 `$1`。[完整替換表](https://code.claude.com/docs/zh-TW/skills.md#available-string-substitutions) 另外加入了具名引數與 `${CLAUDE_*}` 變數
* [注入動態上下文](https://code.claude.com/docs/zh-TW/skills.md#inject-dynamic-context)：`` !`command` `` 行在 Claude 看到 Skill 內容之前運行
* [選擇 Skills 加載的位置](https://code.claude.com/docs/zh-TW/skills.md#where-skills-live)：每個 Skill 位置、外掛命名空間以及兩個共享名稱時哪個 Skill 運行

## 相關資源

* [Claude Code 中的命令](https://code.claude.com/docs/zh-TW/commands.md)：完整的命令表面，包括每個內置命令
* [Agent Skills 概述](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)：概念概述、優勢和架構
* [Agent Skills 最佳實踐](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)：有效 Skills 的編寫指南
* [Agent Skills Cookbook](https://platform.claude.com/cookbook/skills-notebooks-01-skills-introduction)：示例 Skills 和模板
* [SDK 中的子代理](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md)：類似的基於文件系統的代理，具有編程選項
* [SDK 概述](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md)：一般 SDK 概念
* [TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md)：完整 API 文件
* [Python SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md)：完整 API 文件

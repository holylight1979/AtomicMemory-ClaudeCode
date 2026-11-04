<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/migration-guide | lastmod: 2026-10-09 | section: Agent SDK / Agent SDK -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/migration-guide（官方 zh-TW，lastmod 2026-10-09）｜分類：Agent SDK › Agent SDK｜EN 摘要：Guide for migrating the Claude Code TypeScript and Python SDKs to the Claude Agent SDK

# 遷移至 Claude Agent SDK

> 將 Claude Code TypeScript 和 Python SDK 遷移至 Claude Agent SDK 的指南

## 概述

Claude Code SDK 已重新命名為 **Claude Agent SDK**，其文件已重新組織。此變更反映了該 SDK 在建構 AI agent 方面的更廣泛功能，不僅限於編碼任務。

從 OpenAI Agents SDK 遷移？[OpenAI Agents SDK 遷移配方](https://platform.claude.com/cookbook/claude-agent-sdk-04-migrating-from-openai-agents-sdk)透過單一實作範例將每個原始元素對應到 Claude Agent SDK。

## 有什麼改變

| 方面 | 舊版 | 新版 |
| :- | :- | :- |
| **套件名稱 (TS/JS)** | `@anthropic-ai/claude-code` | `@anthropic-ai/claude-agent-sdk` |
| **Python 套件** | `claude-code-sdk` | `claude-agent-sdk` |
| **文件位置** | Claude Code 文件 | Claude Code 文件 → 專用的 [Agent SDK](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 部分 |

## 遷移步驟

### 遷移 TypeScript 或 JavaScript 專案

**1. 解除安裝舊套件：**

```bash theme={null}
npm uninstall @anthropic-ai/claude-code
```

**2. 安裝新套件：**

```bash theme={null}
npm install @anthropic-ai/claude-agent-sdk
```

**3. 更新您的匯入：**

將所有匯入從 `@anthropic-ai/claude-code` 變更為 `@anthropic-ai/claude-agent-sdk`：

```typescript theme={null}
// 之前
import { query, tool, createSdkMcpServer } from "@anthropic-ai/claude-code";

// 之後
import { query, tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";
```

**4. 更新 package.json：**

如果 `@anthropic-ai/claude-code` 仍列在您的 `package.json` 中，請將其替換為 `@anthropic-ai/claude-agent-sdk` 並同時更新版本範圍，例如從 `"^0.0.42"` 更新為 `"^0.3.0"`。

**5. 檢閱[重大變更](#breaking-changes)**

進行任何必要的程式碼變更以完成遷移。

### 遷移 Python 專案

**1. 解除安裝舊套件：**

```bash theme={null}
pip uninstall -y claude-code-sdk
```

如果舊套件未安裝，pip 會列印 `WARNING: Skipping claude-code-sdk as it is not installed.` 這是預期的行為，您可以繼續進行下一步。

**2. 安裝新套件：**

```bash theme={null}
pip install claude-agent-sdk
```

如果 `claude-code-sdk` 列在您的 `requirements.txt` 或 `pyproject.toml` 中，請將其替換為 `claude-agent-sdk`。

**3. 更新您的匯入：**

將所有匯入從 `claude_code_sdk` 變更為 `claude_agent_sdk`：

```python theme={null}
# 之前
from claude_code_sdk import query, ClaudeCodeOptions

# 之後
from claude_agent_sdk import query, ClaudeAgentOptions
```

**4. 檢閱[重大變更](#breaking-changes)**

進行任何必要的程式碼變更以完成遷移。

## 破壞性變更

> [!WARNING]
>
> 為了改進隔離和明確的設定，Claude Agent SDK v0.1.0 為從 Claude Code SDK 遷移的使用者引入了破壞性變更。

### Python：ClaudeCodeOptions 重新命名為 ClaudeAgentOptions

**變更內容：** Python SDK 類型 `ClaudeCodeOptions` 已重新命名為 `ClaudeAgentOptions`。

**遷移：**

```python theme={null}
# BEFORE (claude-code-sdk)
from claude_code_sdk import query, ClaudeCodeOptions

options = ClaudeCodeOptions(model="claude-opus-4-7", permission_mode="acceptEdits")

# AFTER (claude-agent-sdk)
from claude_agent_sdk import query, ClaudeAgentOptions

options = ClaudeAgentOptions(model="claude-opus-4-7", permission_mode="acceptEdits")
```

### 系統提示詞不再為預設值

**變更內容：** SDK 不再預設使用 Claude Code 的系統提示詞。

**遷移：**

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

// BEFORE (v0.0.x) - 預設使用 Claude Code 的系統提示詞
const before = query({ prompt: "Hello" });

// AFTER (v0.1.0) - 預設使用最小系統提示詞
// 若要取得舊版行為，請明確要求 Claude Code 的預設值：
const presetResult = query({
  prompt: "Hello",
  options: {
    systemPrompt: { type: "preset", preset: "claude_code" }
  }
});

// 或使用自訂系統提示詞：
const customResult = query({
  prompt: "Hello",
  options: {
    systemPrompt: "You are a helpful coding assistant"
  }
});
```

```python Python theme={null}
from claude_agent_sdk import query, ClaudeAgentOptions
import asyncio


async def main():
    # BEFORE (v0.0.x) - 預設使用 Claude Code 的系統提示詞
    async for message in query(prompt="Hello"):
        print(message)

    # AFTER (v0.1.0) - 預設使用最小系統提示詞
    # 若要取得舊版行為，請明確要求 Claude Code 的預設值：
    async for message in query(
        prompt="Hello",
        options=ClaudeAgentOptions(
            system_prompt={"type": "preset", "preset": "claude_code"}  # 使用預設值
        ),
    ):
        print(message)

    # 或使用自訂系統提示詞：
    async for message in query(
        prompt="Hello",
        options=ClaudeAgentOptions(system_prompt="You are a helpful coding assistant"),
    ):
        print(message)


asyncio.run(main())
```

### 設定來源預設值

此預設值在 v0.1.0 中曾短暫變更為不載入任何檔案系統設定，隨後已還原，因此不需要進行遷移操作。

**目前行為：** 在 `query()` 上省略 `settingSources` 會載入使用者、專案和本機檔案系統設定，與 CLI 相符。這包括 `~/.claude/settings.json`、`.claude/settings.json`、`.claude/settings.local.json`、CLAUDE.md 檔案和自訂命令。

若要隔離檔案系統設定執行，請傳遞 `settingSources: []`，或在 Python 中傳遞 `setting_sources=[]`。請參閱[使用 settingSources 控制檔案系統設定](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#control-filesystem-settings-with-settingsources)以了解每個來源載入的內容。

隔離對於 CI/CD 管道、已部署的應用程式、測試環境和多租戶系統特別重要，其中本機自訂設定不應洩漏。

> [!NOTE]
>
> Python SDK 0.1.59 及更早版本將空清單視為與省略選項相同，因此請在依賴 `setting_sources=[]` 之前升級。請參閱 [settingSources 不控制的內容](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#what-settingsources-does-not-control)以了解即使 `settingSources` 為 `[]` 時仍會讀取的輸入。

## 後續步驟

* 探索 [Agent SDK 概述](https://code.claude.com/docs/zh-TW/agent-sdk/overview.md) 以了解可用的功能
* 查看 [TypeScript SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md) 以取得詳細的 API 文件
* 檢閱 [Python SDK 參考](https://code.claude.com/docs/zh-TW/agent-sdk/python.md) 以取得 Python 特定的文件
* 了解 [Custom Tools](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md) 和 [MCP Integration](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md)

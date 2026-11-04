<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/quickstart | lastmod: 2026-10-27 | section: Agent SDK / Agent SDK -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/quickstart（官方 zh-TW，lastmod 2026-10-27）｜分類：Agent SDK › Agent SDK｜EN 摘要：Get started with the Python or TypeScript Agent SDK to build AI agents that work autonomously

# 快速開始

> 使用 Python 或 TypeScript Agent SDK 開始構建能夠自主工作的 AI 代理

使用 Agent SDK 構建一個 AI 代理，它可以讀取您的代碼、發現錯誤並自動修復它們，無需手動干預。

**您將執行的操作：**

1. 使用 Agent SDK 設置項目
2. 創建一個包含一些有缺陷代碼的文件
3. 運行一個代理，自動查找並修復錯誤

## 先決條件

* **Node.js 18.14+** 或 **Python 3.10+**
* 一個 **Anthropic 帳戶**。如果您還沒有帳戶，[在此註冊](https://platform.claude.com/)。

## 設定

**1. 建立專案資料夾**

為此快速入門建立新目錄：

```bash theme={null}
mkdir my-agent
cd my-agent
```

對於您自己的專案，您可以從任何資料夾執行 SDK；預設情況下，它將能夠存取該目錄及其子目錄中的檔案。

**2. 安裝 SDK**

為您的語言安裝 Agent SDK 套件：

> [tab] TypeScript (新專案)
>
> ```bash theme={null}
> npm init -y
> npm pkg set type=module
> npm install @anthropic-ai/claude-agent-sdk
> npm install --save-dev tsx
> ```
>
> 在 `package.json` 中設定 `"type": "module"` 可讓您的代理程式指令碼使用頂層 `await`，而 [tsx](https://tsx.hirok.io) 可直接執行 TypeScript 檔案。npm 在安裝成功時會列印 `added N packages`。

> [tab] TypeScript (現有專案)
>
> ```bash theme={null}
> npm install @anthropic-ai/claude-agent-sdk
> npm install --save-dev tsx
> ```
>
> [tsx](https://tsx.hirok.io) 可直接執行 TypeScript 檔案。如果您的專案使用 CommonJS，請將代理程式指令碼命名為 `agent.mts` 而不是 `agent.ts`。`.mts` 副檔名使 tsx 將檔案視為 ES 模組，因此頂層 `await` 可以正常運作，無需將整個專案轉換為 ES 模組。在本快速入門稍後的建立和執行步驟中，使用 `agent.mts` 代替 `agent.ts`。

> [tab] Python (uv)
>
> [安裝 uv](https://docs.astral.sh/uv/)，一個快速的 Python 套件管理器，可自動處理虛擬環境。然後初始化專案並新增 SDK：
>
> ```bash theme={null}
> uv init
> uv add claude-agent-sdk
> ```

> [tab] Python (pip)
>
> 建立並啟動虛擬環境，然後安裝套件。
>
> 在 macOS 或 Linux 上：
>
> ```bash theme={null}
> python3 -m venv .venv
> source .venv/bin/activate
> pip install claude-agent-sdk
> ```
>
> 在 Windows 上：
>
> ```powershell theme={null}
> py -m venv .venv
> .venv\Scripts\Activate.ps1
> pip install claude-agent-sdk
> ```
>
> 如果 PowerShell 因執行原則錯誤而阻止 `Activate.ps1`，請先執行 `Set-ExecutionPolicy -Scope Process RemoteSigned`。

> [!NOTE]
>
> TypeScript 和 Python SDK 都包含原生 Claude Code 二進位檔，因此大多數安裝不需要單獨安裝 Claude Code。某些安裝沒有包含的二進位檔：
>
> * 如果 pip 安裝 Python SDK 的原始碼發行版而不是平台 wheel（例如在 ARM64 Windows 上），則不會包含二進位檔。[原生安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)。Python SDK 會在您的 `PATH` 上找到它。
> * TypeScript SDK 通過 npm 可選相依性安裝其二進位檔，因此跳過它們的安裝（例如 `npm ci --omit=optional`）即使在支援的平台上也不會獲得二進位檔。重新安裝而不跳過可選相依性，或[原生安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code) 並將 `pathToClaudeCodeExecutable` 設定為其路徑。

**3. 設定您的 API 金鑰**

從 [Claude 主控台](https://platform.claude.com/) 取得 API 金鑰，然後在您將執行代理程式的 shell 中將其設定為環境變數：

> [tab] macOS / Linux
>
> ```bash theme={null}
> export ANTHROPIC_API_KEY=your-api-key
> ```

> [tab] Windows (PowerShell)
>
> ```powershell theme={null}
> $env:ANTHROPIC_API_KEY = "your-api-key"
> ```

SDK 從執行您的代理程式的程序環境中讀取金鑰；它不會自動載入 `.env` 檔案。如果您將金鑰保存在 `.env` 檔案中，請自行載入它，例如使用 `dotenv` 套件，然後再呼叫 SDK。

SDK 也支援透過第三方 API 提供者進行驗證：

* **Amazon Bedrock**：設定 `CLAUDE_CODE_USE_BEDROCK=1` 環境變數並設定 AWS 認證
* **AWS 上的 Claude Platform**：設定 `CLAUDE_CODE_USE_ANTHROPIC_AWS=1` 和 `ANTHROPIC_AWS_WORKSPACE_ID`，然後設定 AWS 認證
* **Google Cloud 的 Agent Platform**：設定 `CLAUDE_CODE_USE_VERTEX=1` 環境變數並設定 Google Cloud 認證
* **Microsoft Foundry**：設定 `CLAUDE_CODE_USE_FOUNDRY=1` 環境變數並設定 Azure 認證

如需詳細資訊，請參閱 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md)、[AWS 上的 Claude Platform](https://code.claude.com/docs/zh-TW/claude-platform-on-aws.md)、[Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 或 [Microsoft Foundry](https://code.claude.com/docs/zh-TW/microsoft-foundry.md) 的設定指南。

> [!NOTE]
>
> 除非事先獲得批准，否則 Anthropic 不允許第三方開發人員為其產品（包括基於 Claude Agent SDK 建立的 agent）提供 claude.ai 登入或速率限制。請改用本文件中描述的 API 金鑰驗證方法。

## 創建有缺陷的文件

此快速開始將引導您構建一個可以查找並修復代碼中的錯誤的代理。首先，您需要一個包含一些故意錯誤的文件供代理修復。在 `my-agent` 目錄中創建 `utils.py` 並粘貼以下代碼：

```python theme={null}
def calculate_average(numbers):
    total = 0
    for num in numbers:
        total += num
    return total / len(numbers)


def get_user_name(user):
    return user["name"].upper()
```

此代碼有兩個錯誤：

1. `calculate_average([])` 因除以零而崩潰
2. `get_user_name(None)` 因 TypeError 而崩潰

## 建立一個尋找並修復錯誤的代理

如果您使用 Python SDK，請建立 `agent.py`；如果使用 TypeScript，請建立 `agent.ts`。如果您現有的專案使用 CommonJS，請改用 `agent.mts`：

```python Python theme={null}
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage


async def main():
    # Agentic loop: streams messages as Claude works
    async for message in query(
        prompt="Review utils.py for bugs that would cause crashes. Fix any issues you find.",
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Edit", "Glob"],  # Auto-approve these tools
            permission_mode="acceptEdits",  # Auto-approve file edits
        ),
    ):
        # Print human-readable output
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text"):
                    print(block.text)  # Claude's reasoning
                elif hasattr(block, "name"):
                    print(f"Tool: {block.name}")  # Tool being called
        elif isinstance(message, ResultMessage):
            print(f"Done: {message.subtype}")  # Final result


asyncio.run(main())
```

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

// Agentic loop: streams messages as Claude works
for await (const message of query({
  prompt: "Review utils.py for bugs that would cause crashes. Fix any issues you find.",
  options: {
    allowedTools: ["Read", "Edit", "Glob"], // Auto-approve these tools
    permissionMode: "acceptEdits" // Auto-approve file edits
  }
})) {
  // Print human-readable output
  if (message.type === "assistant" && message.message?.content) {
    for (const block of message.message.content) {
      if ("text" in block) {
        console.log(block.text); // Claude's reasoning
      } else if ("name" in block) {
        console.log(`Tool: ${block.name}`); // Tool being called
      }
    }
  } else if (message.type === "result") {
    console.log(`Done: ${message.subtype}`); // Final result
  }
}
```

此程式碼有三個主要部分：

1. **`query`**：主要進入點，建立代理迴圈。它會傳回非同步迭代器，因此您可以使用 `async for` 在 Claude 工作時串流訊息。請參閱 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#query) 或 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#query) SDK 參考中的完整 API。

2. **`prompt`**：您想讓 Claude 執行的任務。Claude 會根據任務判斷要使用哪些工具。

3. **`options`**：代理的設定。此範例使用 `allowedTools` 預先核准 `Read`、`Edit` 和 `Glob`，並使用 `permissionMode: "acceptEdits"` 自動核准檔案變更。其他選項包括 `systemPrompt`、`mcpServers` 等。請參閱 [Python](https://code.claude.com/docs/zh-TW/agent-sdk/python.md#claudeagentoptions) 或 [TypeScript](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#options) 的所有選項。

`async for` 迴圈會持續執行，因為 Claude 思考、呼叫工具、觀察結果，並決定接下來要做什麼。每次迭代都會產生一條訊息：Claude 的推理、工具呼叫、工具結果或最終結果。SDK 會處理協調、工具執行、內容管理和重試，因此您只需使用串流。當 Claude 完成任務或遇到錯誤時，迴圈就會結束。

迴圈內的訊息處理會篩選出人類可讀的輸出。如果不進行篩選，您會看到原始訊息物件，包括系統初始化和內部狀態，這對除錯很有用，但在其他情況下會很雜亂。

> [!NOTE]
>
> 此範例使用串流來即時顯示進度。如果您不需要即時輸出（例如，用於背景工作或 CI 管道），您可以一次收集所有訊息。如需詳細資訊，請參閱[串流與單回合模式](https://code.claude.com/docs/zh-TW/agent-sdk/streaming-vs-single-mode.md)。

### 執行您的代理

您的代理已準備好。使用下列命令執行它：

> [tab] TypeScript
>
> ```bash theme={null}
> npx tsx agent.ts
> ```
>
> 如果您將指令碼命名為 `agent.mts`，請改為執行 `npx tsx agent.mts`。

> [tab] Python (uv)
>
> ```bash theme={null}
> uv run agent.py
> ```

> [tab] Python (pip)
>
> 在您的虛擬環境仍然啟用的情況下：
>
> ```bash theme={null}
> python agent.py
> ```

在執行時，代理會列印其推理和它呼叫的每個工具，最後以 `Done: success` 結束。執行後，檢查 `utils.py`。您會看到防禦性程式碼處理空清單和空值使用者。您的代理自主地：

1. **讀取** `utils.py` 以了解程式碼
2. **分析**邏輯並識別會導致當機的邊界情況
3. **編輯**檔案以新增適當的錯誤處理

這就是 Agent SDK 的不同之處：Claude 直接執行工具，而不是要求您實作它們。

> [!NOTE]
>
> 如果您看到驗證錯誤，例如 `Not logged in` 或 `Invalid API key`，請確保您已在執行代理的 shell 中設定 `ANTHROPIC_API_KEY` 環境變數。SDK 不會自動載入 `.env` 檔案。
>
> 如需這些和其他驗證錯誤的原因和修復方法，請參閱錯誤參考中的[驗證錯誤](https://code.claude.com/docs/zh-TW/errors.md#authentication-errors)。

### 嘗試其他提示

現在您的代理已設定好，請嘗試一些不同的提示：

* `"Add docstrings to all functions in utils.py"`
* `"Add type hints to all functions in utils.py"`
* `"Create a README.md documenting the functions in utils.py"`

### 自訂您的代理

您可以透過變更選項來修改代理的行為。以下是一些範例：

**新增網路搜尋功能：**

```python Python theme={null}
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Edit", "Glob", "WebSearch"], permission_mode="acceptEdits"
)
```

```typescript TypeScript hidelines={1,-1} theme={null}
const _ = {
  options: {
    allowedTools: ["Read", "Edit", "Glob", "WebSearch"],
    permissionMode: "acceptEdits"
  }
};
```

**給 Claude 一個自訂系統提示：**

```python Python theme={null}
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Edit", "Glob"],
    permission_mode="acceptEdits",
    system_prompt="You are a senior Python developer. Always follow PEP 8 style guidelines.",
)
```

```typescript TypeScript hidelines={1,-1} theme={null}
const _ = {
  options: {
    allowedTools: ["Read", "Edit", "Glob"],
    permissionMode: "acceptEdits",
    systemPrompt: "You are a senior Python developer. Always follow PEP 8 style guidelines."
  }
};
```

**在終端機中執行命令：**

```python Python theme={null}
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Edit", "Glob", "Bash"], permission_mode="acceptEdits"
)
```

```typescript TypeScript hidelines={1,-1} theme={null}
const _ = {
  options: {
    allowedTools: ["Read", "Edit", "Glob", "Bash"],
    permissionMode: "acceptEdits"
  }
};
```

啟用 `Bash` 後，請嘗試：`"Write unit tests for utils.py, run them, and fix any failures"`

每個這些程式碼片段都會在同一個選項物件上設定欄位。如需更多資訊，請參閱[設定您的代理](https://code.claude.com/docs/zh-TW/agent-sdk/configuration.md)。

## 關鍵概念

**工具**控制您的代理可以執行的操作：

| 工具 | 代理可以執行的操作 |
| - | - |
| `Read`、`Glob`、`Grep` | 只讀分析 |
| `Read`、`Edit`、`Glob` | 分析和修改代碼 |
| `Read`、`Edit`、`Bash`、`Glob`、`Grep` | 完全自動化 |

**權限模式**控制您想要多少人工監督。SDK 會按照固定順序評估活躍模式以及您的允許和拒絕規則，詳見[權限如何被評估](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md#how-permissions-are-evaluated)。如需完整的模式列表、其行為以及何時使用各個模式，請參閱[代理迴圈如何運作中的權限模式](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#permission-mode)。

## 後續步驟

現在您已建立了第一個代理程式，請了解如何擴展其功能並根據您的使用案例進行客製化：

* **[設定您的代理程式](https://code.claude.com/docs/zh-TW/agent-sdk/configuration.md)**：組合選項物件並找到涵蓋每個設定的頁面
* **[權限](https://code.claude.com/docs/zh-TW/agent-sdk/permissions.md)**：控制您的代理程式可以執行的操作以及何時需要批准
* **[Hooks](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)**：在工具呼叫之前或之後執行自訂程式碼
* **[Sessions](https://code.claude.com/docs/zh-TW/agent-sdk/sessions.md)**：建立維持上下文的多輪代理程式
* **[MCP servers](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md)**：連接到資料庫、瀏覽器、API 和其他外部系統
* **[Hosting](https://code.claude.com/docs/zh-TW/agent-sdk/hosting.md)**：將代理程式部署到 Docker、雲端和 CI/CD
* **[Example agents](https://github.com/anthropics/claude-agent-sdk-demos)**：查看完整範例：電子郵件助手、研究代理程式等
* **[Troubleshooting](https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting.md)**：修復 CLI 無法啟動或退出時的錯誤，或結果未能以結構化輸出形式到達時的問題

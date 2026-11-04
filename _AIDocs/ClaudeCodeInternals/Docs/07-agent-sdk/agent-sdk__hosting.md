<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/hosting | lastmod: 2026-10-27 | section: Agent SDK / Deployment -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/hosting（官方 zh-TW，lastmod 2026-10-27）｜分類：Agent SDK › Deployment｜EN 摘要：Deploy the Agent SDK in production: subprocess architecture, session persistence, scaling, observability, and multi-tenant isolation for Docker, Kubernetes, and sandbox providers.

# 代理 SDK 的託管

> 在生產環境中部署 Agent SDK：子程序架構、工作階段持久化、擴展、可觀測性，以及針對 Docker、Kubernetes 和沙箱提供者的多租戶隔離。

Agent SDK 會生成並監督一個 `claude` CLI 子程序，該子程序擁有一個 shell、一個工作目錄和磁碟上的工作階段檔案。託管它不像託管無狀態 API 包裝器。每個執行中的代理都是一個與本地狀態相關聯的長期執行程序，這決定了您如何分配資源、持久化工作階段以及跨租戶進行擴展。

本頁涵蓋在您自己的基礎設施上進行自我託管。如需可部署的 Dockerfile 和 Kubernetes 清單，請參閱[託管食譜](https://github.com/anthropics/claude-cookbooks/tree/main/claude_agent_sdk/hosting)。

如果您不需要在自己的基礎設施上執行代理迴圈本身，請改為考慮[受管代理](https://platform.claude.com/docs/en/managed-agents/overview)。Anthropic 託管代理迴圈，您的應用程式透過用戶端 SDK 或 REST API 發送事件並接收串流結果。工具執行在 Anthropic 管理的雲端沙箱或您自己基礎設施上的[自我託管沙箱](https://platform.claude.com/docs/en/managed-agents/self-hosted-sandboxes)中執行。

## 子程序模型

此頁面上的每個託管決策都遵循 SDK 如何執行代理的方式。當您的程式碼呼叫 `query()` 時，SDK 會產生一個獨立的 `claude` CLI 子程序，並透過 stdio 與其通訊。該子程序擁有 shell、工作目錄和本機磁碟上的 JSONL 工作階段文字記錄。

![Request flow: client to your app, which spawns a claude CLI subprocess over stdio inside the container; the subprocess writes to local disk and calls api.anthropic.com over HTTPS](https://mintcdn.com/claude-code/ikqp3_70mqIahteV/images/agent-sdk/hosting-subprocess.svg?fit=max\&auto=format\&n=ikqp3_70mqIahteV\&q=85\&s=9dac857ca9d3b1410c3734900c386004)

一個代理工作階段對應一個子程序。執行 N 個並行工作階段意味著 N 個子程序，每個都有自己的程序樹和文字記錄檔案。預設情況下，它們都繼承您應用程式的工作目錄。當工作階段需要獨立的檔案系統時，在每個工作階段的 `query()` 呼叫選項中傳遞不同的 `cwd`：

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

for await (const message of query({
  prompt: "Summarize the files in this directory",
  options: { cwd: "/work/session-a" },
})) {
  console.log(message);
}
```

```python Python theme={null}
import asyncio

from claude_agent_sdk import ClaudeAgentOptions, query


async def main():
    async for message in query(
        prompt="Summarize the files in this directory",
        options=ClaudeAgentOptions(cwd="/work/session-a"),
    ):
        print(message)


asyncio.run(main())
```

此頁面上的 TypeScript 範例使用頂層 `await`，因此請將它們儲存為 `.mts` 檔案或在 `package.json` 中設定 `"type": "module"`。

### 存放在本機磁碟上的狀態

三種代理狀態預設存放在容器的檔案系統上。它們都無法在容器重新啟動、縮減或移至不同節點時存活。

| 狀態 | 預設位置 |
| - | - |
| 工作階段文字記錄 | `~/.claude/projects/`，或如果設定了 `CLAUDE_CONFIG_DIR`，則為其下的 `projects/` 目錄 |
| `CLAUDE.md` 記憶檔案 | 使用者層級的 `~/.claude/CLAUDE.md` 和專案層級的工作階段工作目錄 |
| 工作目錄成品 | 工作階段的工作目錄 |

若要在主機之間保留文字記錄，請設定 [`SessionStore` 配接器](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage)。記憶檔案和其他工作目錄成品需要自己的儲存策略，例如掛載的磁碟區或物件存放區同步。

如需了解工作階段、復原和分支在 API 層級如何運作，請參閱[工作階段](https://code.claude.com/docs/zh-TW/agent-sdk/sessions.md)。

## 選擇工作階段模式

這四種模式涵蓋工作階段生命週期：容器相對於其服務的工作階段存在多長時間。關於容器執行的位置，[託管食譜](https://github.com/anthropics/claude-cookbooks/blob/main/claude_agent_sdk/07_Hosting_the_agent.ipynb)提供了[可部署的程式碼](https://github.com/anthropics/claude-cookbooks/tree/main/claude_agent_sdk/hosting)，用於本機 Docker、Modal 和 Kubernetes。在此選擇工作階段模式，並從食譜中選擇部署目標。

### 短暫工作階段

為每個使用者任務建立一個容器，並在任務完成時銷毀它。最適合一次性任務。使用者仍然可以在任務完成時與 AI 互動，但一旦完成，容器就會被銷毀。

範例工作負載包括錯誤調查和修復、發票和收據提取、文件翻譯和媒體轉換。

容器執行一個一次性進入點，從 `TASK_PROMPT` 環境變數讀取任務，呼叫 SDK，然後退出。

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

const prompt = process.env.TASK_PROMPT!;
for await (const message of query({ prompt, options: { maxTurns: 20 } })) {
  console.log(message);
}
```

```python Python theme={null}
import asyncio
import os

from claude_agent_sdk import ClaudeAgentOptions, query


async def main():
    async for message in query(
        prompt=os.environ["TASK_PROMPT"],
        options=ClaudeAgentOptions(max_turns=20),
    ):
        print(message)


asyncio.run(main())
```

指令碼會在每條訊息到達時列印它，包括當任務在轉數限制內完成時 `subtype` 為 `success` 的結果訊息。如果任務改為達到 20 轉限制，結果訊息的 `subtype` 為 `error_max_turns`，且 `query()` 呼叫在產生它後會引發錯誤，因此如果容器需要乾淨地退出，請將迴圈包裝在 try 區塊中。請參閱[處理結果](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#handle-the-result)以了解錯誤子類型。

### 長期執行工作階段

執行持久容器實例，通常每個容器託管多個 SDK 程序，以服務持續進行的工作。最適合採取自主行動、提供內容或處理高容量訊息流的代理。

範例工作負載包括對傳入郵件進行分類和回應的電子郵件代理、透過容器連接埠託管每個使用者可編輯網站的網站建構器，以及處理來自 Slack 等平台的持續流量的聊天機器人。

容器公開 HTTP 或 WebSocket 端點，並將每個活躍工作階段對應到長期執行的查詢及其背後的子程序。保持工作階段開啟和就緒的呼叫在 SDK 之間有所不同：

* **TypeScript**：使用 [`streamInput()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#query-object) 將轉數新增到活躍工作階段。呼叫 [`startup()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#startup) 在傳入流量前預熱子程序。如果您在第一個請求到達之前不知道工作階段的工作目錄，請改用 [`prewarm()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#prewarm) 進行預熱。
* **Python**：使用 [`ClaudeSDKClient`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudesdkclient) 在轉數間保持工作階段開啟。

調整容器大小，使其能夠在記憶體中保持最大並行工作階段數。

### 混合工作階段

短暫容器，在啟動時從 [`SessionStore`](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage) 補充，並將更新持久化回去。最適合跨越許多互動但在它們之間處於閒置狀態的工作階段。容器在閒置期間關閉，當使用者返回時重新啟動。

範例工作負載包括具有間歇性檢查的個人專案管理器、在數小時內暫停和繼續的深度研究，以及在互動間加載票證歷史記錄的客戶支援代理。

根據您預期使用者返回的頻率調整您提供者的閒置逾時。在沒有配置 `SessionStore` 的情況下關閉容器會遺失其轉錄，因此存放區對於此模式是必需的，而不是可選的。

該模式取決於透過 ID 使用附加的共享存放區繼續工作階段：

```typescript TypeScript theme={null}
import { query, type SessionStore } from "@anthropic-ai/claude-agent-sdk";

declare const userInput: string;
declare const sessionId: string;          // looked up from your database by user
declare const sessionStore: SessionStore; // an object store, key-value store, database, or your own adapter

for await (const message of query({
  prompt: userInput,
  options: { resume: sessionId, sessionStore },
})) {
  // ...
}
```

```python Python theme={null}
from claude_agent_sdk import query, ClaudeAgentOptions, SessionStore
import asyncio

user_input: str = ...
session_id: str = ...              # looked up from your database by user
session_store: SessionStore = ...  # an object store, key-value store, database, or your own adapter


async def main():
    async for message in query(
        prompt=user_input,
        options=ClaudeAgentOptions(
            resume=session_id,
            session_store=session_store,
        ),
    ):
        ...


asyncio.run(main())
```

### 多代理容器

在一個容器內執行多個 SDK 子程序。最適合必須密切協作的代理，例如多代理模擬，其中代理在共享環境中彼此互動。

為每個代理提供自己的工作目錄，以便它們不會覆蓋彼此的檔案，並隔離設定加載，以便每個代理的 `CLAUDE.md` 檔案不會洩漏到其他代理。請參閱[多租戶隔離](#multi-tenant-isolation)以了解特定選項。

## 佈建容器

### 容器型沙箱

在沙箱容器內執行 SDK，以實現程序隔離、資源限制、網路控制和暫時性檔案系統。

選擇提供者時需要回答的問題：

* **誰執行沙箱**：沙箱即服務提供者為您操作基礎設施，而自託管選項則提供軟體供您在自己的環境中執行。
* **冷啟動延遲**：從「建立沙箱」到「準備好接受第一個請求」需要多長時間。暫時性模式需要次秒級啟動。長期執行模式可以容忍更長的延遲。
* **持久儲存**：提供者是否提供耐久磁碟區或僅提供暫時性磁碟。混合模式需要在沙箱內或沙箱旁邊的某處進行耐久儲存。
* **定價模式**：按秒、按請求或按小時固定計費。按秒定價適合突發性暫時性工作負載。按小時定價適合長期執行的工作階段。
* **網路**：支援自訂出站規則、出站代理和私有 VPC 對等互連，適用於受管制的環境。

如需自託管選項（例如 Docker、gVisor 和 Firecracker）以及詳細的隔離設定，請參閱[隔離技術](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md#isolation-technologies)。

### 執行時相依性

容器需要您的 SDK 的語言執行時：

* Python SDK 需要 Python 3.10+，或 TypeScript SDK 需要 Node.js 18.14+
* TypeScript 和 Python SDK 都為大多數安裝捆綁了原生 Claude Code 二進位檔，生成的 CLI 不需要單獨的 Node.js 安裝。請參閱[快速入門的安裝說明](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md)，了解需要單獨原生 Claude Code 安裝的安裝方式。

捆綁的二進位檔會固定到 SDK 套件版本，因此更新 SDK 是更新 CLI 的方式。SDK 遵循語義版本控制：持續採用修補程式版本，並在採用次要版本之前檢閱 [TypeScript](https://github.com/anthropics/claude-agent-sdk-typescript/blob/main/CHANGELOG.md) 或 [Python](https://github.com/anthropics/claude-agent-sdk-python/blob/main/CHANGELOG.md) 變更日誌。

### 資源

每個代理的 1 GiB 記憶體、5 GiB 磁碟和 1 個 CPU 是新啟動執行個體的合理起點。記憶體使用量會隨著工作階段長度和工具活動而增加，因此應根據您實際需要的工作階段長度和並行性進行調整，而不是根據閒置基準。請參閱[擴展和並行性](#scaling-and-concurrency)，了解如何計算每個主機的代理數量。

### 網路

SDK 需要對 `api.anthropic.com` 的出站 HTTPS，或在 Amazon Bedrock 或 Google Cloud 的代理平台上執行時對提供者的區域端點的出站 HTTPS。如果您的代理使用 [MCP 伺服器](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md)或外部工具，它們也需要對這些端點的出站存取。在生產環境中，透過出站代理路由出站流量，該代理強制執行網域允許清單、注入認證並記錄請求。請參閱[安全部署](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md)了解完整模式。

對於入站流量，在容器上公開 HTTP 或 WebSocket 連接埠。您的應用程式在該連接埠上處理用戶端請求並在內部呼叫 SDK；子程序本身不在網路上接聽。

## 處理生產環境的考量

在部署自託管代理程式之前，請先完成這些決策。

### 工作階段和狀態持久化

預設的本機磁碟在重新啟動、縮減規模或移至不同節點時會遺失。對於使用者期望能繼續進行的任何工作階段，請使用 [`SessionStore` 配接器](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage)將文字記錄鏡像到持久儲存體。請參閱[參考實作](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage.md#reference-implementations)以取得物件存放區、鍵值存放區和資料庫的範例配接器，以及用於您自己實作的一致性測試套件。

關於 `SessionStore` 的行為方式，有三件事需要了解：

* **僅限文字記錄**：`SessionStore` 鏡像文字記錄，而不是 `CLAUDE.md` 記憶檔案或其他工作目錄成品。請掛載共用磁碟區或分別同步這些檔案。
* **鏡像，而非替代**：子程序先寫入本機磁碟，然後 SDK 將每個批次的副本轉送到存放區。新工作階段的本機文字記錄比執行時間更長；從存放區繼續執行的工作階段會在結束時刪除其本機副本，因此存放區保有唯一的持久副本。請參閱[雙寫入架構](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage.md#dual-write-architecture)。
* **`mirror_error` 訊息**：當 SDK 無法將批次傳遞到存放區時，它會捨棄該批次、發出 `{ type: "system", subtype: "mirror_error" }` 訊息，並繼續查詢。如果存放區持久性很重要，請對這些訊息發出警示。請參閱[鏡像寫入是盡力而為](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage.md#mirror-writes-are-best-effort)以了解重試和逾時行為。

### 可觀測性

Agent SDK 代理程式是長期執行的程序，會在許多 API 往返中產生工具呼叫。沒有遙測，您無法看到哪些工具執行了、執行時間有多長，或工作階段在何處停滯。

SDK 從環境繼承 OpenTelemetry 設定。在容器或協調器層級設定 OTEL 環境變數，以便每個 `query()` 呼叫都將跨度、指標和日誌事件匯出到您的收集器。下面的範例為所有三個信號啟用 OTLP 匯出。`CLAUDE_CODE_ENHANCED_TELEMETRY_BETA` 僅對追蹤是必需的；如果您只匯出指標和日誌，請省略它。

```bash title=".env" theme={null}
CLAUDE_CODE_ENABLE_TELEMETRY=1
CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=otlp
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=http://collector.example.com:4318
```

預設情況下，匯出中不包含提示文字和工具輸入。請參閱[控制匯出中的敏感資料](https://code.claude.com/docs/zh-TW/agent-sdk/observability.md#control-sensitive-data-in-exports)以取得選擇加入旗標，以及[可觀測性](https://code.claude.com/docs/zh-TW/agent-sdk/observability.md)以取得完整的信號目錄。

### 驗證和密鑰

在託管時，有三個驗證考量很重要：

* **Anthropic API**：子程序從其環境讀取 `ANTHROPIC_API_KEY`。從您的密鑰管理員提供它，或設定 `ANTHROPIC_BASE_URL` 以透過在容器外注入金鑰的代理路由模型呼叫。請參閱[認證管理](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md#credential-management)以了解代理模式，以及 [SDK 快速入門中的設定](https://code.claude.com/docs/zh-TW/agent-sdk/quickstart.md#setup)以了解支援的驗證方法。
* **入站**：在代理程式容器前面的閘道放置驗證。代理程式應接收預先驗證的請求，不應是驗證使用者權杖的元件。
* **出站工具**：將工具認證保留在代理程式環境之外。透過在請求離開容器後注入 API 金鑰的代理路由出站呼叫。代理程式進行呼叫；代理新增認證。

### 縮放和並行

每個工作階段在其自己的子程序中執行，因此主機上的並行受限於其 RAM 可以容納多少個子程序。

使用此公式調整每個主機的大小：

```text theme={null}
agents per host = (host RAM - overhead) / (per-session RAM ceiling)
```

透過執行代表性工作階段至您的目標長度（在您預期的工具負載下）並記錄峰值 RSS 來測量每個工作階段的上限。[資源](#resources)中的 1 GiB 起點是下限，而非上限。

水平縮放路由取決於您的模式。對於長期執行的工作階段（其中容器保有許多工作階段），在負載平衡器後面執行容器池，並使用 `sessionId` 上的一致雜湊將每個工作階段固定到一個容器。固定的工作階段會持續命中同一個容器，因此會命中同一個執行中的子程序，直到它被驅逐或容器重新啟動。

### 成本

Anthropic 權杖成本通常主導容器基礎設施成本一個數量級或更多。最小化佈建的容器大約每小時執行 \$0.05，而單一長代理程式工作階段可能花費數美元的權杖。請參閱[成本追蹤](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md)以進行每個工作階段的權杖計帳。

### 多租戶隔離

預設 SDK 行為從檔案系統讀取設定和 `CLAUDE.md` 記憶檔案。在為多個租戶提供服務的共用容器中，這些檔案可能會將一個租戶的內容洩漏到另一個租戶的工作階段中。

若要隔離共用容器內的租戶：

* 在 TypeScript 中傳遞 `settingSources: []` 或在 Python 中傳遞 `setting_sources=[]` 以跳過使用者、專案和本機設定。
* 在 `env` 中設定 `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`。[自動記憶](https://code.claude.com/docs/zh-TW/memory.md#auto-memory)位於 `~/.claude/projects/<project>/memory/` 會載入系統提示，無論 `settingSources` 為何。請參閱 [settingSources 不控制的內容](https://code.claude.com/docs/zh-TW/agent-sdk/claude-code-features.md#what-settingsources-does-not-control)以了解無條件載入的其他輸入。
* 將 `CLAUDE_CONFIG_DIR` 指向每個租戶目錄，以便租戶不共用 `~/.claude.json` 全域設定。當每個設定目錄提供一個工作目錄，且您不在租戶間共用 [`SessionStore`](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage) 時，您也可以在 `env` 中設定 [`CLAUDE_CODE_PROJECT_DIR_NAME`](https://code.claude.com/docs/zh-TW/sessions#name-the-project-directory-yourself) 以保持其下的文字記錄路徑簡短。需要 TypeScript Agent SDK v0.3.234 或更新版本，或 Python Agent SDK v0.2.140 或更新版本。
* 使用每個租戶的工作目錄。在每個 `query()` 呼叫上明確傳遞 `cwd`。
* 在您的代理應用每個租戶的出站規則，例如不同的出站 IP、認證或網域允許清單，以便受損的租戶無法透過另一個租戶的出站原則進行資料外洩。

下面的範例一起應用設定、自動記憶、設定目錄和工作目錄選項。建構 `tenantDir` 和 `configDir`，以便每個租戶取得沒有其他租戶可以讀取的路徑。在 TypeScript 中，`env` 替代子程序環境，因此展開 `...process.env` 以保留繼承的變數，例如 `PATH` 和 `ANTHROPIC_API_KEY`。在 Python 中，`env` 會合併到繼承的環境之上。

```typescript TypeScript theme={null}
import { query } from "@anthropic-ai/claude-agent-sdk";

declare const prompt: string;
declare const tenantDir: string;
declare const configDir: string;

for await (const message of query({
  prompt,
  options: {
    cwd: tenantDir,
    settingSources: [],
    env: {
      ...process.env,
      CLAUDE_CONFIG_DIR: configDir,
      CLAUDE_CODE_DISABLE_AUTO_MEMORY: "1",
    },
  },
})) {
  // ...
}
```

```python Python theme={null}
from claude_agent_sdk import query, ClaudeAgentOptions
import asyncio

prompt: str = ...
tenant_dir: str = ...
config_dir: str = ...


async def main():
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            cwd=tenant_dir,
            setting_sources=[],
            env={
                "CLAUDE_CONFIG_DIR": config_dir,
                "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            },
        ),
    ):
        ...


asyncio.run(main())
```

## 已知限制

在您的部署設計中規劃這些限制。

| 限制 | 處理方式 |
| - | - |
| 沒有頂層工作階段逾時 | 工作階段不會自動逾時。在 TypeScript 中設定 `maxTurns` 或在 Python 中設定 `max_turns`，以限制 agent 在停止前進行多少個[回合](https://code.claude.com/docs/zh-TW/agent-sdk/agent-loop.md#turns-and-messages)。 |
| 長工作階段中的記憶體成長 | 限制工作階段長度或定期回收子程序。請參閱[擴展和並行](#scaling-and-concurrency)。 |
| 大規模平行子代理程式展開可能會觸及速率限制 | 將工作分成較小的批次，而不是發出一次寬廣的分派。 |
| 沒有每個子代理程式的牆上時鐘截止時間 | 在其 `AgentDefinition` 中使用 `maxTurns` 限制每個[子代理程式](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md)。`CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS` 設定一個停滯監視程式，當子代理程式停止產生輸出時觸發；它不是總執行時間截止時間。 |

## 排除部署失敗

當在已部署的服務中執行的代理程式在您的機器上運作正常但失敗時，請使用本節。下面的每一項都列出一個失敗情況並連結到涵蓋該情況的項目：

* **服務啟動時找不到 CLI**：在 Python 中，容器或服務管理員使用與您的 shell 不同的 `PATH` 來執行您的應用程式，因此在本機運作的安裝對該程序不可見。在 TypeScript 中，映像建置跳過了 SDK 的選用相依性，或 `pathToClaudeCodeExecutable` 指向映像中不存在的檔案。請參閱 [Claude Code not found](https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting.md#clinotfounderror-claude-code-not-found)。
* **CLI 存在於映像中但無法啟動**：Claude Code 無法從與容器架構或 libc 不相符的二進位檔案啟動，或從在映像建置中失去執行權限的檔案啟動。請參閱 [Failed to start Claude Code](https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting.md#cliconnectionerror-failed-to-start-claude-code)。
* **Claude Code 程序在執行中途退出**：您的應用程式收到的錯誤取決於 SDK 語言以及 CLI 是否先報告了錯誤結果。[CLI 程序退出](https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting.md#cli-process-exit) 下的項目涵蓋每條訊息。

## 後續步驟

* [託管食譜](https://github.com/anthropics/claude-cookbooks/blob/main/claude_agent_sdk/07_Hosting_the_agent.ipynb)：包含 Docker、Modal 和 Kubernetes 的[可部署程式碼](https://github.com/anthropics/claude-cookbooks/tree/main/claude_agent_sdk/hosting)的筆記本逐步解說。
* [工作階段儲存](https://code.claude.com/docs/zh-TW/agent-sdk/session-storage.md)：使用 `SessionStore` 配接器在主機間保留文字記錄。
* [可觀測性](https://code.claude.com/docs/zh-TW/agent-sdk/observability.md)：將 OTEL 追蹤、指標和日誌匯出到您的收集器。
* [安全部署](https://code.claude.com/docs/zh-TW/agent-sdk/secure-deployment.md)：網路控制、認證管理和隔離強化。
* [成本追蹤](https://code.claude.com/docs/zh-TW/agent-sdk/cost-tracking.md)：每個工作階段的權杖和成本計帳。

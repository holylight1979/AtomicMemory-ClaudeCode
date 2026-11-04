<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting | lastmod: 2026-10-20 | section: Agent SDK / Agent SDK -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/troubleshooting（官方 zh-TW，lastmod 2026-10-20）｜分類：Agent SDK › Agent SDK｜EN 摘要：Fix Agent SDK errors when the Claude Code CLI fails to start, the CLI process exits, or a successful result arrives without structured output.

# 排除 Agent SDK 的故障

> 當 Claude Code CLI 無法啟動、CLI 程序退出或成功結果到達但沒有結構化輸出時，修復 Agent SDK 錯誤。

此頁面涵蓋 CLI 啟動、CLI 程序退出和結構化輸出中的 Agent SDK 錯誤。此頁面上的項目按您看到的錯誤進行分類。每個項目都說明原因和解決方法。

與功能相關的症狀，例如 hook 未觸發或 skill 未被使用，在該功能的頁面上有故障排除部分。下表列出涵蓋每個症狀的部分或頁面：

| 症狀 | 前往 |
| :- | :- |
| 找不到 Skills、skill 未被使用、`Invalid skill name` 錯誤 | [Skills 故障排除](https://code.claude.com/docs/zh-TW/agent-sdk/skills.md#troubleshooting) |
| MCP 伺服器顯示 `failed` 狀態、工具未被呼叫、SDK MCP 伺服器中缺少某個工具、連線逾時、工具輸出超過允許的最大 token 數 | [MCP 疑難排解](https://code.claude.com/docs/zh-TW/agent-sdk/mcp.md#troubleshooting) |
| Plugin 未載入、plugin skills 未出現 | [Plugins 故障排除](https://code.claude.com/docs/zh-TW/agent-sdk/plugins.md#troubleshooting) |
| Claude 未委派給子代理、基於檔案系統的代理未載入 | [Subagents 故障排除](https://code.claude.com/docs/zh-TW/agent-sdk/subagents.md#troubleshooting) |
| Checkpointing 選項未被識別、使用者訊息沒有 UUID、`No file checkpoint found`、`File rewinding is not enabled`、`ProcessTransport is not ready for writing` | [檔案 checkpointing 故障排除](https://code.claude.com/docs/zh-TW/agent-sdk/file-checkpointing.md#troubleshooting) |
| Hook 未觸發、matcher 未如預期篩選、hook 逾時、工具意外被阻止、修改的輸入未被應用、Python 中無法使用工作階段 hooks、子代理權限提示增加、子代理的遞迴 hook 迴圈、`systemMessage` 未出現在輸出中 | [修復常見問題](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md#fix-common-issues)（在 hooks 頁面上） |
| 在您的機器上運作的代理在已部署的服務或容器中失敗 | [故障排除部署失敗](https://code.claude.com/docs/zh-TW/agent-sdk/hosting.md#troubleshoot-deployment-failures) |
| `Not logged in`、`Invalid API key`、`API Error`、`429`、`There's an issue with the selected model` | [錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#find-your-error) |
| `CLINotFoundError`、`CLIConnectionError`、`ProcessError`、`Claude Code process exited with code N`、`Claude Code returned an error result`、`structured_output` 是 `None` | 此頁面上的 [CLI 啟動](#cli-startup)、[CLI 程序退出](#cli-process-exit) 和 [結構化輸出](#structured-outputs) |

## CLI 啟動

### CLINotFoundError: Claude Code not found

Python SDK 將 Claude Code CLI 作為子程序啟動。當它找不到 `claude` 可執行檔時，連線會失敗並出現 `CLINotFoundError`：

```
Claude Code not found at: /your/configured/path
```

當您設定 `ClaudeAgentOptions(cli_path=...)` 且它指向遺失的檔案時，訊息會包含設定的路徑。沒有 `cli_path` 時，SDK 會搜尋您的 `PATH` 和常見安裝位置，訊息會包含您平台的安裝說明。

若要修復：

* 如果尚未安裝 Claude Code，請安裝。請參閱[安裝 Claude Code](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)以取得您平台上的命令。
* 如果您設定了 `cli_path`，請確認檔案存在且是 `claude` 可執行檔。
* 如果您依賴 `PATH` 解析，請確認 `claude --version` 在您的應用程式執行的相同環境中有效。您在 shell 外啟動的程序（例如從 IDE 或服務管理員），通常會以不同的 `PATH` 執行。

TypeScript SDK 在其捆綁的平台套件和您在 `pathToClaudeCodeExecutable` 中設定的路徑中尋找 CLI。符合您看到的訊息：

* `Native CLI binary for <platform>-<arch> not found`：捆綁的平台套件遺失，最常見的原因是安裝跳過了可選依賴項。重新安裝 `@anthropic-ai/claude-agent-sdk` 而不跳過可選依賴項，或將 `pathToClaudeCodeExecutable` 指向[原生安裝](https://code.claude.com/docs/zh-TW/setup.md#install-claude-code)。在使用 `bun build --compile` 建立的單一檔案可執行檔中，相同的訊息有不同的原因和修復。請參閱[編譯為單一可執行檔](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#compile-to-a-single-executable)。
* `Claude Code native binary not found at <path>` 或 `Claude Code executable not found at <path>. Is options.pathToClaudeCodeExecutable set?`：已解析路徑上的檔案遺失，或程序無法存取它。確認檔案存在於該路徑且程序可以存取它。

### CLIConnectionError: Refusing to execute batch script

在 Windows 上，當 Python SDK 使用的 CLI 路徑是 `.bat` 或 `.cmd` 批次指令碼（包括 npm 安裝建立的 `claude.cmd` 填充程式）時，連線會失敗並出現 `CLIConnectionError`：

```
Refusing to execute batch script 'C:\\Users\\you\\AppData\\Roaming\\npm\\claude.cmd': Windows runs .bat/.cmd files via cmd.exe, which can execute commands injected through CLI arguments, and no reliable escaping for cmd.exe exists. Use a native claude executable instead: install Claude Code natively (irm https://claude.ai/install.ps1 | iex), point ClaudeAgentOptions(cli_path=...) at a claude.exe, or install the claude-agent-sdk wheel for a platform that bundles claude.exe (e.g. Windows x64).
```

拒絕是刻意的安全強化，不是破損的安裝。Windows 通過將生成重寫為 `cmd.exe /c` 呼叫來執行批次指令碼，而 `cmd.exe` 在執行時重新解析整個命令列，因此引數值可以執行注入的命令。

大多數 Windows 安裝永遠不會達到此錯誤。`claude-agent-sdk` 的 Windows x64 wheel 捆綁了 `claude.exe`，SDK 優先使用捆綁的 CLI，然後是它可以發現的任何原生 `claude.exe`，最後才回退到批次填充程式。您在兩種情況下會看到拒絕：

* 您將 `ClaudeAgentOptions(cli_path=...)` 設定為 `.bat` 或 `.cmd` 檔案，例如 npm 的 `claude.cmd` 填充程式。
* 您的安裝沒有捆綁或原生 `claude.exe`，例如 ARM64 Windows 上的原始碼安裝，其中您的 `PATH` 上唯一的 `claude` 是 npm 填充程式。

若要修復，請給 SDK 一個原生可執行檔而不是批次指令碼：

* 如果您設定了 `ClaudeAgentOptions(cli_path=...)`，請將其指向 `claude.exe` 或移除該選項。當設定了 `cli_path` 時，SDK 會跳過發現，因此單獨的原生安裝無法生效。
* 在 PowerShell 中原生安裝 Claude Code：`irm https://claude.ai/install.ps1 | iex`
* 在 x64 Windows 上，安裝捆綁 `claude.exe` 的 `claude-agent-sdk` wheel。

在 `claude-agent-sdk` 0.2.124 之前，Python SDK 通過 `cmd.exe` 生成批次指令碼而沒有此檢查。

### CLIConnectionError: Failed to start Claude Code

SDK 在已解析的路徑上找到了檔案，但無法啟動它。Python 將這些失敗作為 `CLIConnectionError` 引發。TypeScript 以不帶 SDK 類別的錯誤拒絕訊息迭代。下表將每個訊息對應到它告訴您的內容。符合您看到的訊息：

| 訊息 | SDK | 它告訴您什麼 |
| - | - | - |
| `Failed to start Claude Code: <detail>` | Python | 訊息的其餘部分是作業系統本身的錯誤 |
| `Claude Code executable at <path> exists but failed to launch` | TypeScript | 設定路徑上的指令碼無法執行 |
| `Claude Code native binary at <path> exists but failed to launch` | TypeScript | 二進位檔案無法執行，訊息附加了 libc 建議 |
| `Failed to spawn Claude Code process: <detail>` | TypeScript | 任何其他啟動失敗 |

在兩個 SDK 中，通常的原因是已解析的路徑指向無法執行的內容，例如文字檔案、目錄或沒有執行權限的檔案。將原生二進位訊息的 libc 建議讀作一個可能的原因。

若要在任一 SDK 中修復：

* 確認設定的路徑指向 `claude` 可執行檔本身，且檔案具有執行權限。
* 如果您不需要自訂路徑，請在 Python 中移除 `cli_path` 或在 TypeScript 中移除 `pathToClaudeCodeExecutable`，以便 SDK 自行尋找 CLI，優先使用其捆綁的副本。
* 當失敗的二進位檔案是容器映像中 SDK 的捆綁副本時，在映像建置期間重新安裝 SDK，以便捆綁的二進位檔案符合容器的平台，或為其執行的架構重建映像。通常的原因是不符合容器架構或 libc 的二進位檔案，或在映像建置中失去執行權限的二進位檔案。

### CLIConnectionError: Not connected

在 Python 中，在用戶端連線之前或斷開連線之後呼叫 `ClaudeSDKClient` 方法會引發帶有此訊息的 `CLIConnectionError`：

```
Not connected. Call connect() first.
```

按照訊息所說的做。在任何其他用戶端方法之前呼叫 `await client.connect()`，或使用 `async with ClaudeSDKClient() as client:` 開啟用戶端，它在進入時連線。

## CLI 程序退出

本節中的項目表示 Claude Code 程序在您的應用程式使用它時結束。您看到的錯誤取決於 SDK 語言以及 CLI 在退出前是否報告了錯誤結果。

### ProcessError: Command failed with exit code

當 Claude Code 程序以非零代碼退出時，Python SDK 會引發 `ProcessError`：

```
Command failed with exit code 1 (exit code: 1)
Error output: Check stderr output for details
```

訊息陳述退出代碼兩次，`Error output` 行是固定文字而不是您程序的錯誤輸出。相同的固定文字填充異常的 `stderr` 屬性。異常的 `exit_code` 屬性攜帶代碼。若要捕獲 CLI 實際寫入 stderr 的內容，請在 `ClaudeAgentOptions` 中傳遞 `stderr` 回呼並記錄它接收的內容。

裸露的 `ProcessError` 表示 CLI 退出而未報告錯誤結果。當 CLI 確實報告了一個時，SDK 會改為引發[`ResultError`](https://code.claude.com/docs/zh-TW/agent-sdk/python#resulterror)，涵蓋在[Claude Code returned an error result](#claude-code-returned-an-error-result)。`ResultError` 是 `ProcessError` 的子類別，因此 `except ProcessError` 會捕獲兩者。若要以不同方式處理它們，請先放置 `except ResultError` 子句。

在 `claude-agent-sdk` 0.2.140 之前，Python SDK 將錯誤結果退出作為普通 `Exception` 而不是 `ResultError` 引發。

### Claude Code process exited with code N

IDE 包裝程式也會列印此訊息，[錯誤參考](https://code.claude.com/docs/zh-TW/errors.md#claude-code-process-exited-with-code-n)涵蓋了 VS Code 和其他啟動程式的內容。此項目涵蓋您的 TypeScript SDK 程式碼接收的內容。SDK 將非零 CLI 退出表面為普通 `Error`，它拒絕 `query()` 訊息上的 `for await` 迴圈。沒有 SDK 錯誤類別可捕獲，因此將迴圈包裝在 `try`/`catch` 中並符合訊息：

```
Claude Code process exited with code 1. stderr: <tail of the CLI's stderr>
```

當 CLI 寫入 stderr 時，訊息以其尾部結尾。若要捕獲完整串流，請在查詢選項中傳遞 `stderr` 回呼。被信號殺死的程序以相同形式報告 `Claude Code process terminated by signal <name>`。

### Claude Code returned an error result

當 CLI 在退出前報告錯誤結果時，兩個 SDK 都會用此訊息替換程序退出錯誤：

```
Claude Code returned an error result: <the CLI's own error report>
```

冒號後的文字是 CLI 對出錯原因的報告，因此從那裡開始而不是從退出本身開始。Python 將此作為[`ResultError`](https://code.claude.com/docs/zh-TW/agent-sdk/python#resulterror)引發，其 `data` 屬性攜帶完整的錯誤結果。TypeScript 以帶有相同訊息形狀的普通 `Error` 拒絕訊息迴圈。

## 結構化輸出

### structured\_output is None but the result says success

結果訊息可以以 `subtype: "success"` 結尾，而在 Python 中 `structured_output` 是 `None` 或在 TypeScript 中是 `undefined`。執行完成，但不存在驗證的輸出。

在應用程式程式碼中將此結果視為失敗。在使用 `structured_output` 之前，檢查 `subtype` 是 `success` 且 `structured_output` 存在。[錯誤處理](https://code.claude.com/docs/zh-TW/agent-sdk/structured-outputs.md#error-handling)部分顯示了兩個 SDK 的此模式。接著檢查以下原因：

* **Claude 拒絕的請求**：若要在程式碼中偵測此情況，請檢查結果訊息的 `stop_reason` 是否為 `"refusal"`。關於接下來可嘗試的做法，請參閱 [Usage Policy 拒絕](https://code.claude.com/docs/zh-TW/errors.md#usage-policy-refusal)。
* **沒有任何輸出能滿足的 schema**：例如，`minLength` 大於其 `maxLength` 的字串。如果在您認為正確的 schema 下 `structured_output` 反覆缺失，請尋找彼此矛盾的約束。如果找不到，請簡化 schema 直到輸出通過驗證，然後一次重新引入一個約束。

## 報告新問題

如果您的錯誤未在此涵蓋，請檢查開啟的問題或在 SDK 儲存庫中提交新問題：[claude-agent-sdk-typescript](https://github.com/anthropics/claude-agent-sdk-typescript/issues) 或 [claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python/issues)。包括完整的錯誤文字和您的 SDK 版本。

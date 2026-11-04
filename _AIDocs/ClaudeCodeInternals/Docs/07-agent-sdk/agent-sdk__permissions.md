<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/agent-sdk/permissions | lastmod: 2026-10-27 | section: Agent SDK / Control and observability -->
> 來源：https://code.claude.com/docs/zh-TW/agent-sdk/permissions（官方 zh-TW，lastmod 2026-10-27）｜分類：Agent SDK › Control and observability｜EN 摘要：Control how your agent uses tools with permission modes, hooks, and declarative allow/deny rules.

# 設定權限

> 使用權限模式、hooks 和宣告式允許/拒絕規則來控制您的代理程式如何使用工具。

Claude Agent SDK 提供權限控制來管理 Claude 如何使用工具。使用權限模式和規則來定義自動允許的內容，以及使用 [`canUseTool` callback](https://code.claude.com/docs/zh-TW/agent-sdk/user-input) 來在執行時處理其他所有情況。

## 權限如何被評估

> [!NOTE]
>
> 如果您載入包含 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 的外掛，請參閱 [mod 的決定在規則與 hook 之間的位置](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

當 Claude 請求一個工具時，SDK 按照以下順序檢查權限：

**1. Hooks**

首先執行 [hooks](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)。Hook 可以直接拒絕呼叫或將其傳遞下去。返回 `allow` 的 hook 不會跳過下面的拒絕和詢問規則；無論 hook 結果如何，這些規則都會被評估。

返回 `allow` 的 `PreToolUse` hook 也無法核准目標被 Claude Code 識別為[關鍵路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)的 `rm` 或 `rmdir` 命令，例如 `rm -rf ~`。關於該 `allow` 在 plan mode 中的作用，請參閱 [plan mode 中的 hook 核准](https://code.claude.com/docs/zh-TW/permissions.md#hook-approvals-in-plan-mode)。

**2. 拒絕規則**

如果來自 `disallowed_tools` 或 [settings.json](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings) 的拒絕規則匹配，呼叫會被拒絕，且不會呼叫 [`canUseTool`](https://code.claude.com/docs/zh-TW/agent-sdk/user-input)，即使在 [`bypassPermissions`](#bypass-permissions-mode-bypasspermissions) 模式下，以及即使 hook 返回了 `allow` 也是如此。

在 TypeScript SDK 中，如果您將[自訂工具](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools.md#require-approval-for-specific-tools)的 `permission_policy` 設定為 [`always_deny`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#mcpservertoolpolicy)，對該工具的呼叫會在此步驟被拒絕。

**3. 詢問規則**

檢查來自 [settings.json](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings) 的 `ask` 規則。如果詢問規則匹配，呼叫會傳遞到您的 [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/user-input) 以進行確認，即使在 `bypassPermissions` 模式下也是如此。

需要使用者互動的工具行為相同：`AskUserQuestion` 和 MCP 工具（其伺服器設定了 [`_meta["anthropic/requiresUserInteraction"]`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool)）總是傳遞到回呼，即使當 allow 規則匹配時也是如此。在 `dontAsk` 模式下，兩種情況都會被拒絕，因為該模式永遠不會提示。MCP 註解需要 Claude Code v2.1.199 或更新版本。

您的組織設定為 `ask` 的 [claude.ai connector](https://code.claude.com/docs/zh-TW/mcp.md#organization-controls-on-connector-tools) 工具也會在此步驟離開流程。每個呼叫都會傳遞到回呼，即使在 `bypassPermissions` 模式下，即使當 allow 規則匹配時也是如此。回呼會收到原因 `Your organization requires approval for this tool`。在 `dontAsk` 模式下，呼叫會被拒絕，因為該模式永遠不會提示。

在 TypeScript SDK 中，如果您將自訂工具的 `permission_policy` 設定為 [`always_ask`](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools#require-approval-for-specific-tools)，任何 allow 規則都不會核准其呼叫，即使是 `allowedTools` 條目也不會。在 `dontAsk` 模式下，Claude Code 會拒絕這些呼叫；而在 `auto`、`plan` 或 `bypassPermissions` 模式下，它[可以在您的回呼執行之前核准它們](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#permission-modes-that-can-approve-an-always_ask-call)。

**4. 權限模式**

應用活躍的 [權限模式](#permission-modes)：

* 在 `bypassPermissions` 模式下，Claude Code 核准到達此步驟的所有內容，但經識別的[關鍵路徑移除](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)以及被標記為 [`Dangerous rm operation not ruled out`](https://code.claude.com/docs/zh-TW/permission-modes#dangerous-rm-operation-not-ruled-out) 的 Bash 命令除外，這些會改為傳遞下去。
  * 若要在沒有提示的情況下執行這些移除，請參閱[關閉關鍵路徑移除提示](https://code.claude.com/docs/zh-TW/permission-modes.md#turn-off-the-critical-path-removal-prompt-in-bypasspermissions-mode)。
* 在 `acceptEdits` 模式下，Claude Code 核准 [接受編輯模式](#accept-edits-mode-acceptedits) 下列出的檔案操作。
* 在 `plan` 模式下，Claude Code 將檔案編輯工具發送到您的 `canUseTool` 回呼，無論 allow 規則如何。
* 在其他模式下，請求會傳遞下去。

**5. 允許規則**

檢查 `allow` 規則（來自 `allowed_tools` 和 settings.json）。如果規則匹配，工具會被核准。工具自行核准的呼叫也會在此步驟解決，無需規則：例如在您的工作目錄內的檔案讀取或 [唯讀 Bash 命令](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)。

經識別的[關鍵路徑移除](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)不會被 allow 規則核准，而被標記為 `Dangerous rm operation not ruled out` 的命令也不會被 `Bash` 或 `Bash(*)` 規則核准。它們是否隨後到達您的回呼取決於權限模式：例如在 `auto` 模式的 Agent SDK 工作階段中，Claude Code 預設會拒絕它們而不呼叫它。[關鍵路徑模式表](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-path-removals-in-each-permission-mode)列出了每個模式對它們的處理方式。

Allow 規則不會核准從 [網路路徑](https://code.claude.com/docs/zh-TW/permissions.md#network-paths) 進行的讀取。

**6. canUseTool 回呼**

如果上述任何步驟都未解決，請呼叫您的 [`canUseTool` 回呼](https://code.claude.com/docs/zh-TW/agent-sdk/user-input) 以獲得決定。在 `dontAsk` 模式下，此步驟會被跳過，工具會被拒絕，不過您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准[部分此類呼叫](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

在 TypeScript SDK 中，如果您設定了 [`permissionPrompts: 'none'`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#options)，您的回呼在此步驟不會被呼叫。[`PermissionRequest` hook](https://code.claude.com/docs/zh-TW/hooks#permissionrequest) 仍然有機會決定，如果它不決定，Claude Code 會拒絕呼叫。此選項需要 Claude Code v2.1.259 或更新版本。

![六步權限評估流程的圖表，與上述步驟相符：工具請求通過 hooks、拒絕規則、詢問規則、權限模式、允許規則和 canUseTool。Hooks、拒絕規則和 canUseTool 可以路由到被阻止；權限模式繞過、允許規則和 canUseTool 可以路由到執行；詢問規則路由到 canUseTool。](https://mintcdn.com/claude-code/jYgs7qigNjO1Badj/images/agent-sdk/permissions-flow.svg?fit=max\&auto=format\&n=jYgs7qigNjO1Badj\&q=85\&s=c771ad9085b1277d3708027a49c744bc)

如果您在 TypeScript SDK 期望評估順序在諮詢回呼之前自動批准呼叫的設定中傳遞 `canUseTool` 回呼，SDK 會在構造查詢時發出一次 Node.js 程序警告。警告的代碼是 `CLAUDE_SDK_CAN_USE_TOOL_SHADOWED`。兩個設定會觸發它：

* `permissionMode: 'bypassPermissions'`：警告文字以 `canUseTool will not be invoked: permissionMode 'bypassPermissions'` 開頭。工具呼叫會在諮詢 `canUseTool` 之前被核准，因此您的回呼只會針對少數呼叫執行，例如 [Bypass permissions 模式](#bypass-permissions-mode-bypasspermissions)下列出的呼叫。若也要檢查已核准的呼叫，請將回呼的檢查放在 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks) 中
* 僅為工具名稱的 `allowedTools` 條目，例如 `"Read"`：警告會在 `canUseTool will not be invoked for:` 之後列出每個此類條目。對所列工具的呼叫會在諮詢 `canUseTool` 之前被核准，但 [allow 規則永遠不會核准的呼叫](#calls-an-allow-rule-never-approves)除外。若要讓您的回呼針對所列工具中需要核准的呼叫執行，請從 `allowedTools` 中移除該工具的條目

具有指定符的條目（如 `Bash(ls *)`）和 `acceptEdits` 模式不會觸發它，來自設定檔的 allow 規則對檢查不可見。

此警告不會阻擋任何呼叫，也不會變更任何選項。如果您的回呼已經會收到您想檢查的每個呼叫，請維持設定不變。若要記錄此警告，請使用 `process.on('warning', ...)` 進行監聽並匹配 `CLAUDE_SDK_CAN_USE_TOOL_SHADOWED` 代碼。

此頁面重點關注 **allow 和 deny 規則** 以及 **權限模式**。對於其他步驟：

* **Hooks：** 執行自訂程式碼以允許、拒絕或修改工具請求。請參閱 [使用 hooks 控制執行](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)。
* **canUseTool 回呼：** 在執行時提示使用者批准，當沒有較早的步驟解決呼叫時。請參閱 [處理批准和使用者輸入](https://code.claude.com/docs/zh-TW/agent-sdk/user-input.md)。

## 允許和拒絕規則

`allowed_tools` 和 `disallowed_tools`（TypeScript：`allowedTools` / `disallowedTools`）在上述評估流程中新增允許和拒絕規則清單的項目。如果您在 `allowed_tools` 中命名其中一個[任務追蹤工具](https://code.claude.com/docs/zh-TW/agent-sdk/todo-tracking.md#model-availability)，Claude Code 也會為該工作階段啟用這些工具。任何未列在 `allowed_tools` 中的其他工具仍可供 Claude 使用，對其進行的需要批准的呼叫會進入權限模式。拒絕規則的行為取決於它們是命名工具還是在工具內限定模式。

| 選項 | 效果 |
| :- | :- |
| `allowed_tools=["Read", "Grep"]` | `Read` 和 `Grep` 會自動核准，但[從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)除外。此處未列出的其他工具仍然存在，對它們進行的需要核准的呼叫會進入權限模式和 `canUseTool`。 |
| `disallowed_tools=["Bash"]` | `Bash` 工具定義會從請求中移除。Claude 看不到該工具，無法嘗試使用它。 |
| `disallowed_tools=["Bash(rm *)"]` | `Bash` 保持可用。符合 `rm *` [如所寫](https://code.claude.com/docs/zh-TW/permissions.md#bash-rule-limits)的呼叫在每個權限模式中都會被拒絕，包括 `bypassPermissions`。其他 `Bash` 呼叫（包括 `/bin/rm`）會進入權限模式。 |
| `disallowed_tools=["*"]` | 每個工具定義都會從請求中移除。拒絕規則支援工具名稱萬用字元：`"*"` 符合每個工具，`"mcp__*"` 符合所有伺服器上的每個 MCP 工具。 |

允許規則僅在字面 `mcp__<server>__` 前綴之後接受工具名稱萬用字元。伺服器段必須無萬用字元，以便規則命名您設定的特定伺服器：`mcp__puppeteer__*` 符合來自 `puppeteer` 伺服器的每個工具，`mcp__github__get_*` 符合其 `get_` 工具。未錨定的項目（如 `allowed_tools=["*"]` 或 `allowed_tools=["mcp__*"]`）會被忽略，不會自動核准任何內容。

`Read` 和 `Edit` 的限定規則採用路徑模式。`Edit(path)` 規則管理所有寫入檔案的內建工具，包括 `Write` 和 `NotebookEdit`；`Write(path)` 規則永遠不會被檔案權限檢查符合。

使用 `//path` 表示絕對檔案系統路徑：`Edit(//secrets/**)` 的拒絕規則會阻止在磁碟上 `/secrets` 下任何位置的寫入。使用單個前導斜線時，`Edit(/secrets/**)` 會在規則的來源處錨定。對於透過 `allowed_tools` 或 `disallowed_tools` 傳遞的規則，這表示工作階段的工作目錄，因此規則不會阻止磁碟上的 `/secrets`。請參閱[讀取和編輯規則](https://code.claude.com/docs/zh-TW/permissions.md#read-and-edit)以了解四種錨定形式以及來自設定檔的規則如何解析。

> [!WARNING]
>
> **自動批准的工具永遠不會到達 `canUseTool`。** 在任何較早步驟中批准的工具呼叫，透過 `acceptEdits` 或 `bypassPermissions`，或透過允許規則，會跳過您的 `canUseTool` 回呼，因此您在那裡放置的權限檢查會被該工具無聲地繞過。
>
> 如果對 `allowed_tools` 中某個工具的呼叫仍會到達您的 `canUseTool` 回呼，或在 `dontAsk` 模式中遭到拒絕，請檢查它們是否為[從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)，或屬於下列呼叫。沒有任何允許規則會核准這些呼叫。在永不提示的 `dontAsk` 模式中，Claude Code 會拒絕這些呼叫而不呼叫 `canUseTool`；在其他權限模式中，請依各項目的說明處理：
>
> * `AskUserQuestion`、標記為 [`_meta["anthropic/requiresUserInteraction"]`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具，以及[您的組織設定為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具：在回呼中回應它們。[處理釐清問題](https://code.claude.com/docs/zh-TW/agent-sdk/user-input.md#handle-clarifying-questions)說明如何回應 `AskUserQuestion`，而連接器呼叫抵達時會附帶原因 `Your organization requires approval for this tool`
>
> * 您的應用程式標記為 [`always_ask`](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools#require-approval-for-specific-tools) 的自訂工具：在回呼中決定該呼叫。若要停止這些呼叫抵達，請[在工作階段中途變更政策](https://code.claude.com/docs/zh-TW/agent-sdk/typescript.md#mcpsdkserverconfigwithinstance)。在 `auto`、`plan` 和 `bypassPermissions` 模式中，該呼叫也可能在回呼之前就被核准，相關情況列於[可核准 `always_ask` 呼叫的權限模式](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#permission-modes-that-can-approve-an-always_ask-call)
>
> * 經辨識的 `rm` 和 `rmdir` [關鍵路徑移除](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)：在 `default`、`acceptEdits` 和 `bypassPermissions` 模式中，請在回呼中允許或拒絕該移除，此時 [`decisionReason`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#canusetool) 會以 `Dangerous rm` 開頭。關於 `auto` 和 `plan` 模式，請參閱[各權限模式中的關鍵路徑移除](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-path-removals-in-each-permission-mode)。辨識這些移除的檢查[可能會遺漏某些命令](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)
>
> * **裸名稱**：像 `Read` 或 `mcp__github__get_issue` 這樣的項目會自動核准對該工具的每個呼叫，但[任何模式都不自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)和[從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)除外。
>
> * **限定規則**：像 `Bash(npm test *)` 這樣的項目只會自動核准符合的呼叫，其他需要核准的 `Bash` 呼叫仍會進入回呼。
>
> 對於必須在每個工具呼叫上執行的檢查，請使用 [`PreToolUse` hook](https://code.claude.com/docs/zh-TW/agent-sdk/hooks)：hook 在每個其他步驟之前執行，hook 拒絕即使在 `bypassPermissions` 模式中也適用。

對於鎖定的代理，將 `allowedTools` 與 `permissionMode: "dontAsk"` 配對：

```typescript theme={null}
const options = {
  allowedTools: ["Read", "Glob", "Grep"],
  permissionMode: "dontAsk"
};
```

列出的 `Read`、`Glob` 和 `Grep` 呼叫會被核准，但[任何模式都不自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)和[從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)除外。其他每個原本會提示的呼叫則會被拒絕，不過您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准[其中部分呼叫](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。

在 `default` 模式中不需要核准的呼叫無論您是否列出都會執行。這些呼叫包括[唯讀 Bash 命令](https://code.claude.com/docs/zh-TW/permissions.md#read-only-commands)、不在執行前詢問的工具（如 `Agent`），以及工作目錄內的檔案讀取。若要對 Claude 完全隱藏某個內建工具，而非拒絕其呼叫，請將其裸名稱新增到 `disallowedTools`。

> [!WARNING]
>
> **`allowed_tools` 不限制 `bypassPermissions`。** `allowed_tools` 預先批准您列出的工具。其他未列出的工具不符合任何允許規則，會進入權限模式，其中 `bypassPermissions` 會批准它們。將 `allowed_tools=["Read"]` 與 `permission_mode="bypassPermissions"` 一起設定仍會批准每個工具，包括 `Bash`、`Write` 和 `Edit`。如果您需要 `bypassPermissions` 但想要阻止特定工具，請使用 `disallowed_tools`。

您也可以在 `.claude/settings.json` 中以宣告方式設定允許、拒絕和詢問規則。當啟用 `project` 設定來源時會讀取這些規則，預設 `query()` 選項就是這樣。如果您明確設定 `setting_sources`（TypeScript：`settingSources`），請包含 `"project"` 以便它們適用。請參閱[權限設定](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings)以了解規則語法。

## 權限模式

權限模式可全域控制 Claude 使用工具的方式。您可以在呼叫 `query()` 時設定權限模式，或在串流工作階段期間動態變更。

使用 Claude Code v2.1.302 或更新版本時，除非您設定了權限模式，或應用程式從其設定檔中的 [`permissions.defaultMode`](https://code.claude.com/docs/zh-TW/settings-reference#permissions-defaultmode) 取得權限模式，否則應用程式會以 `default` 模式啟動。在 `default` 模式下，Claude Code 會拒絕任何需要核准的工具呼叫，除非您透過 allow 規則、hook、`canUseTool` 回呼或權限提示工具核准該呼叫。如果工具呼叫遭到拒絕，請參閱[在 `claude -p` 和 Agent SDK 執行中工具呼叫遭到拒絕](https://code.claude.com/docs/zh-TW/permission-modes#which-mode-a-non-interactive-run-starts-in)。

### 可用模式

SDK 支援以下權限模式：

| 模式 | 說明 | 工具行為 |
| :- | :- | :- |
| `default` | 標準權限行為 | 沒有基於模式的自動核准；需要核准且不符合任何 allow 規則的呼叫會觸發您的 `canUseTool` 回呼 |
| `dontAsk` | 拒絕而非提示 | 任何原本會提示的呼叫都會被拒絕，且不會呼叫 `canUseTool`，不過您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准[其中部分呼叫](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。由 `allowed_tools` 或 `settings.json` allow 規則核准的呼叫會執行，在 `default` 模式下不需要核准的呼叫也會執行。某些呼叫，例如[從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)，即使符合 `allowed_tools` 或 allow 規則也會被拒絕。如需清單，請參閱 [Don't ask 模式](#don’t-ask-mode-dontask) |
| `acceptEdits` | 自動接受檔案編輯 | 檔案編輯和[檔案系統操作](#accept-edits-mode-acceptedits)（`mkdir`、`rm`、`mv` 等）會自動核准 |
| `bypassPermissions` | 略過權限檢查 | 工具會在沒有權限提示的情況下執行，但[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)除外；此外，在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)之外，您的應用程式[標記為 `always_ask`](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools#require-approval-for-specific-tools) 的自訂工具也除外。請謹慎使用 |
| `plan` | 規劃模式 | Claude 會探索並規劃，但不會編輯您的原始檔；檔案編輯永遠不會自動核准，而是透過您的 `canUseTool` 回呼提示 |
| `auto` | 由模型分類的核准 | 模型分類器會審查 shell 命令和網路請求等動作，對其審查的每個動作予以允許或封鎖。如需可用性與決策順序，請參閱[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode) |

> [!WARNING]
>
> **Subagent 繼承：** 如果您的主要工作階段處於 [plan mode](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode)，即使 subagent 的 [`AgentDefinition`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#agentdefinition) 設定了 `permissionMode: "acceptEdits"`，該 subagent 仍會在 plan mode 中執行。該 subagent 對您原始檔的 `Edit` 和 `Write` 呼叫仍會送往您的 `canUseTool` 回呼。Plan mode 對您定義的 subagent 同樣有效，因此將工作交給 subagent 並不能繞過先審查計劃的步驟。
>
> Subagent 會從主要工作階段繼承 `plan`、`acceptEdits`、`auto` 或 `bypassPermissions`；而在 `default` 或 `dontAsk` 模式的主要工作階段下，subagent 會以您設定的模式執行。即便如此，Claude Code 永遠不會套用 `"bypassPermissions"` 值，且只有在該 subagent [可使用自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)時才會套用 `"auto"` 值。`bypassPermissions` 例外需要 Claude Code v2.1.267 或更新版本。
>
> Subagent 可能具有不同的系統提示詞，且行為限制比您的主要 agent 更少，因此繼承 `bypassPermissions` 會授予它們完整、自主的系統存取權。[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)仍然適用。

### 設定權限模式

您可以在開始查詢時設定一次權限模式，也可以在工作階段進行中動態變更。

> [tab] 查詢時
>
> 在建立查詢時傳入 `permission_mode`（Python）或 `permissionMode`（TypeScript）。
>
> ```python Python theme={null}
> import asyncio
> from claude_agent_sdk import query, ClaudeAgentOptions
>
>
> async def main():
>     async for message in query(
>         prompt="Help me refactor this code",
>         options=ClaudeAgentOptions(
>             permission_mode="default",  # Set the mode here
>         ),
>     ):
>         if hasattr(message, "result"):
>             print(message.result)
>
>
> asyncio.run(main())
> ```
>
> ```typescript TypeScript theme={null}
> import { query } from "@anthropic-ai/claude-agent-sdk";
>
> async function main() {
>   for await (const message of query({
>     prompt: "Help me refactor this code",
>     options: {
>       permissionMode: "default" // Set the mode here
>     }
>   })) {
>     if ("result" in message) {
>       console.log(message.result);
>     }
>   }
> }
>
> main();
> ```

> [tab] 串流期間
>
> 呼叫 `set_permission_mode()`（Python）或 `setPermissionMode()`（TypeScript）即可在工作階段中途變更模式。新模式會立即對所有後續的工具請求生效。這讓您可以從嚴格的限制開始，隨著信任建立再逐步放寬權限，例如在審查 Claude 的初步做法後切換至 `acceptEdits`。
>
> ```python Python theme={null}
> import asyncio
> from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
>
>
> async def main():
>     async with ClaudeSDKClient(
>         options=ClaudeAgentOptions(
>             permission_mode="default",  # Start in default mode
>         )
>     ) as client:
>         await client.query("Help me refactor this code")
>
>         # Change mode dynamically mid-session
>         await client.set_permission_mode("acceptEdits")
>
>         # Process messages with the new permission mode
>         async for message in client.receive_response():
>             if hasattr(message, "result"):
>                 print(message.result)
>
>
> asyncio.run(main())
> ```
>
> ```typescript TypeScript theme={null}
> import { query } from "@anthropic-ai/claude-agent-sdk";
>
> async function main() {
>   const q = query({
>     prompt: "Help me refactor this code",
>     options: {
>       permissionMode: "default" // Start in default mode
>     }
>   });
>
>   // Change mode dynamically mid-session
>   await q.setPermissionMode("acceptEdits");
>
>   // Process messages with the new permission mode
>   for await (const message of q) {
>     if ("result" in message) {
>       console.log(message.result);
>     }
>   }
> }
>
> main();
> ```

### 模式詳細資訊

#### Accept edits 模式（`acceptEdits`）

自動核准檔案操作，讓 Claude 無需提示即可編輯程式碼。其他工具（例如非檔案系統操作的 Bash 命令）仍需一般權限。

**自動核准的操作：**

* 檔案編輯（Edit、Write 工具）
* 檔案系統命令：`mkdir`、`touch`、`rm`、`rmdir`、`mv`、`cp`、`sed`

兩者都僅適用於工作目錄或 `additionalDirectories` 內的路徑。在 `acceptEdits` 模式下，當 Claude 進行以下操作時，Claude Code 不會自動核准該請求：

* 處理該範圍之外的路徑
* 寫入受保護的路徑
* 使用 `rm` 或 `rmdir` 移除 Claude Code 識別為[關鍵路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)的路徑
* 執行帶有選項、glob，或 `timeout 5`、`LANG=C` 等前綴的 [`touch`](https://code.claude.com/docs/zh-TW/permission-modes#auto-approve-file-edits-with-acceptedits-mode)

**適用時機：** 您信任 Claude 的編輯並希望加快反覆開發的速度，例如在製作原型期間或在隔離的目錄中工作時。

#### Don't ask 模式（`dontAsk`）

將任何權限提示轉換為拒絕，且不會呼叫 `canUseTool`，不過您安裝的 [mod](https://code.claude.com/docs/zh-TW/plugins/mods/overview.md) 仍可核准[其中部分呼叫](https://code.claude.com/docs/zh-TW/permissions.md#precedence-among-rules-hooks-and-mods)。由 `allowed_tools`、`settings.json` allow 規則或 hook 預先核准的工具會正常執行。在 `default` 模式下不需要核准的呼叫也會正常執行，例如讀取您工作目錄內的檔案以及對 `Agent` 的呼叫。

以下呼叫即使符合 allow 規則也會被拒絕：

* [您的組織設為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具
* 需要使用者互動的工具，例如 `AskUserQuestion`，以及其伺服器設定了 [`_meta["anthropic/requiresUserInteraction"]`](https://code.claude.com/docs/zh-TW/mcp#require-approval-for-a-specific-tool) 的 MCP 工具
* 您的應用程式將其 `permission_policy` 設為 [`always_ask`](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools#require-approval-for-specific-tools) 的自訂工具
* [從網路路徑讀取](https://code.claude.com/docs/zh-TW/permissions.md#network-paths)
* 經識別的[關鍵路徑移除](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)

如果您的 `PreToolUse` hook 對經識別的關鍵路徑移除、從網路路徑讀取，或對標記為 `always_ask` 之工具的呼叫傳回 `allow`，該呼叫仍會被拒絕。識別這些移除操作的檢查[可能會遺漏某些命令](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)。

**適用時機：** 您希望為 headless agent 提供固定且明確的工具範圍，並偏好直接拒絕，而非默默依賴 `canUseTool` 不存在的情況。

#### Bypass permissions 模式（`bypassPermissions`）

無需提示即自動核准工具使用，但[任何模式都不會自動核准的動作](https://code.claude.com/docs/zh-TW/permission-modes.md#actions-no-mode-auto-approves)除外。Hook 仍會執行，並可在必要時封鎖操作。在 Linux 和 macOS 上，若不在[受認可的沙箱](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)中，無論是以 root 身分或透過 `sudo`，Claude Code 都會拒絕以此模式啟動，且查詢會在第一個回合之前失敗。

> [!WARNING]
>
> 請極度謹慎使用。在此模式下，Claude 擁有完整的系統存取權。僅在您信任所有可能操作的受控環境中使用。
>
> `allowed_tools` 不會限制此模式。所有工具都會被核准，而不僅是您列出的工具。以下控制措施仍然適用：
>
> * Deny 規則、明確的 `ask` 規則和 hook 會在模式檢查之前進行評估，且仍可封鎖工具。
> * [您的組織設為 `ask`](https://code.claude.com/docs/zh-TW/mcp#organization-controls-on-connector-tools) 的連接器工具、需要使用者互動的工具，以及經識別的[關鍵路徑移除](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)，仍會交由您的 `canUseTool` 回呼處理。識別這些移除操作的檢查[可能會遺漏某些命令](https://code.claude.com/docs/zh-TW/permission-modes.md#critical-paths)，且您可以[關閉關鍵路徑移除提示](https://code.claude.com/docs/zh-TW/permission-modes.md#turn-off-the-critical-path-removal-prompt-in-bypasspermissions-mode)。在[雲端工作階段](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md)之外，對您的應用程式[標記為 `always_ask`](https://code.claude.com/docs/zh-TW/agent-sdk/custom-tools#require-approval-for-specific-tools) 之自訂工具的呼叫也會交由該回呼處理。
> * [跨工作階段訊息傳遞防護措施](https://code.claude.com/docs/zh-TW/permission-modes.md#skip-all-checks-with-bypasspermissions-mode)仍然適用。

#### Plan mode（`plan`）

Claude 會探索程式碼庫並產生計劃，但不會編輯您的原始檔。在 plan mode 中，檔案編輯永遠不會自動核准，即使符合 allow 規則或 `PreToolUse` hook 傳回 `allow` 也一樣。這些編輯會改為透過您的 `canUseTool` 回呼提示。

當工作階段可使用自動模式時，Claude 在規劃期間執行的命令預設不會送達您的回呼，因為[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)所使用的分類器模型會[改為審查這些命令](https://code.claude.com/docs/zh-TW/permission-modes.md#analyze-before-you-edit-with-plan-mode)。啟用該審查時，分類器也可以核准原本會送達您回呼的唯讀呼叫，例如沒有 allow 規則的 `WebFetch` 呼叫。

> [!NOTE]
>
> 在 TypeScript SDK 中，如果您將 `allowDangerouslySkipPermissions: true` 與 `permissionMode: 'plan'` 一起設定，檔案編輯仍會送達您的 `canUseTool` 回呼。若要之後使用 `setPermissionMode()` 將以 plan mode 啟動的工作階段切換為 `bypassPermissions`，您需要從一開始就設定 `allowDangerouslySkipPermissions`。

Claude 可能會在定案計劃之前使用 `AskUserQuestion` 釐清需求。如需處理這些提示的方式，請參閱[處理核准與使用者輸入](https://code.claude.com/docs/zh-TW/agent-sdk/user-input.md#handle-clarifying-questions)。

**適用時機：** 您希望 Claude 提出變更建議但不執行，例如在程式碼審查期間，或在變更進行之前需要您核准時。

#### 自動模式（`auto`）

分類器模型會在 shell 命令和網路請求等動作執行之前進行審查，並對其審查的每個動作予以允許或封鎖。如需自動模式所需的模型與供應商，以及其評估動作的順序，請參閱[使用自動模式消除權限提示](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)。

如果您使用 [`set_model()`](https://code.claude.com/docs/zh-TW/agent-sdk/python#claudesdkclient)、[`setModel()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#query-object) 或 [`applyFlagSettings()`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#applyflagsettings)，將處於自動模式的工作階段切換至自動模式不支援的模型，工作階段會變更為 `default` 模式：

* **您會看到的內容**：一則 subtype 為 `status`、且 `permissionMode` 設為 `"default"` 的 `system` 訊息，TypeScript SDK 將其型別定義為 [`SDKStatusMessage`](https://code.claude.com/docs/zh-TW/agent-sdk/typescript#sdkstatusmessage)。從此之後，需要核准且不符合任何 allow 規則的呼叫會送達您的 `canUseTool` 回呼。
* **若要回到自動模式**：切換至受支援的模型，然後呼叫 `set_permission_mode("auto")` 或 `setPermissionMode("auto")`。如果您將模型切換回來但未進行該呼叫，工作階段會維持在 `default` 模式。當不受支援的模型處於作用中時，該呼叫會失敗並顯示 `Cannot set permission mode to auto: auto mode unavailable for this model`。

在呼叫 `set_model()`、`setModel()` 或 `applyFlagSettings()` 之後變更為 `default` 模式的行為，需要 Claude Code v2.1.299 或更新版本。

## 相關資源

如需了解權限評估流程中的其他步驟：

* [處理核准和使用者輸入](https://code.claude.com/docs/zh-TW/agent-sdk/user-input.md)：互動式核准提示和澄清問題
* [Hooks 指南](https://code.claude.com/docs/zh-TW/agent-sdk/hooks.md)：在代理程式生命週期中的關鍵點執行自訂程式碼
* [權限規則](https://code.claude.com/docs/zh-TW/settings-reference.md#permission-settings)：`settings.json` 中的宣告式允許/拒絕規則

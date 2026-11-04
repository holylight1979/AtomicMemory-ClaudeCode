<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w35 | lastmod: 2026-09-17 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w35（官方 zh-TW，lastmod 2026-09-17）｜分類：What's New › What's New｜EN 摘要：Resume terminal sessions in the Claude Code Desktop app, review feedback reports that Claude drafts for you, and start a session in restricted mode.

# 第 35 週 · 2026 年 8 月 24–28 日

> 在 Claude Code Desktop 應用程式中復原終端機工作階段、檢閱 Claude 為您起草的意見回饋報告，以及在受限模式中啟動工作階段。

版本 [v2.1.240 → v2.1.250](https://code.claude.com/docs/en/changelog.md#2-1-240)
3 項功能 · 8 月 24–28 日

在 Desktop 應用程式中復原終端機工作階段
Desktop

在 Claude Code Desktop 提示框中輸入 `/resume`，以選擇您從 CLI 啟動的任何工作階段，並在應用程式中繼續進行，保持完整的對話和內容。按標題、資料夾或分支搜尋您的工作階段，並在復原前預覽您停止的位置。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/f9HTZGyMtxIFOUgt/images/whats-new/desktop-resume-cli-session.mp4?fit=max&auto=format&n=f9HTZGyMtxIFOUgt&q=85&s=41e4a5fda6b9d63280589f2cbdabf44f" />

在 Desktop 工作階段中，執行命令以列出您的終端機工作階段：

```text Claude Code theme={null}
> /resume
```

選擇工作階段並按 `Enter`。對話會在您停止的位置在應用程式中開啟。

[在 CLI 和 Desktop 之間移動](https://code.claude.com/docs/zh-TW/desktop.md#coming-from-the-cli)

Claude 起草的意見回饋
CLI

當工具持續失敗、Claude 無法協助請求，或您指出錯誤時，Claude 現在會使用 `SendFeedback` 工具為您起草意見回饋報告。提示上方的卡片會顯示草稿，您可以從那裡檢閱、傳送或關閉它。在您傳送之前，沒有任何內容會到達 Anthropic。需要 v2.1.238 或更新版本。

![Claude Code 工作階段，其中 Claude 已起草標題為「沙箱映像拉取在代理後失敗」的錯誤報告，顯示為提示上方的卡片，具有檢閱、傳送或關閉的選項](https://mintcdn.com/claude-code/f9HTZGyMtxIFOUgt/images/whats-new/claude-drafted-feedback.jpg?fit=max\&auto=format\&n=f9HTZGyMtxIFOUgt\&q=85\&s=5cacb3be0dffd1cbd417381f3721637e)

執行 `/feedback` 且不帶任何引數，以開啟來自每個工作階段的草稿佇列：

```text Claude Code theme={null}
> /feedback
```

選擇草稿，然後編輯、傳送或捨棄它。若要關閉起草功能，請在 `/config` 中將 **Claude 起草的意見回饋**設定為 `off`。

[SendFeedback 工具行為](https://code.claude.com/docs/zh-TW/tools-reference.md#sendfeedback-tool-behavior)

受限模式
v2.1.248

受限模式啟動 Claude Code 時不包含執行命令或程式碼的內建工具。當評估工具在共用機器上驅動 `claude` 時使用它。使用 `--restricted` 啟動或設定 `CLAUDE_CODE_RESTRICTED=1`。Claude Code 也會移除 `WebFetch`、將檔案工具限制在工作目錄、僅載入受管設定和 `--settings`，並拒絕 `bypassPermissions` 權限模式。

執行不具有命令執行工具的非互動式查詢：

```bash terminal theme={null}
claude --restricted -p "review src/ for SQL injection risks"
```

若要將移除的工具之一還原給 Claude，請將其與您想要的其他內建工具一起列在 `--tools` 中，例如 `--tools "Bash,Read,Edit"`。`--tools` 是允許清單，其 `default` 預設值不會復原移除的工具。

[CLI 旗標](https://code.claude.com/docs/zh-TW/cli-reference.md#cli-flags)

其他成果

設定新的 [`modelPicker`](https://code.claude.com/docs/zh-TW/settings-reference#modelpicker) 設定以擴充或取代 `/model` 選擇器的內建清單，包含您自己的有序、標籤化項目，包括 Amazon Bedrock 或 Google Cloud 的 Agent Platform 模型 ID設定 [`promptCacheTtl`](https://code.claude.com/docs/zh-TW/prompt-caching#choose-the-ttl-yourself) 為 `1h`，以在您使用 API 金鑰或雲端提供者時在主對話上保持一小時的提示快取；`subagentPromptCacheTtl` 為子代理和主對話外的所有其他請求設定 TTL在 Pro、Max、Team 和 Enterprise 方案上，[`/usage`](https://code.claude.com/docs/zh-TW/costs#plan-usage-breakdown) 新增迴圈分解：執行計數、總權杖、每次執行的權杖，以及使用最多權杖的 `/loop` 和排程工作的最後執行簽約費率的組織可以設定 [`modelPricing`](https://code.claude.com/docs/zh-TW/costs#report-spend-at-your-contracted-rates) 受管設定，以便 `/usage`、狀態列和 OpenTelemetry 以這些費率而非清單價格報告成本`/login` 在 **Anthropic Console 帳戶**選項下提供 **使用您的 Console 帳戶登入**，因此 Console 組織的成員若不允許 API 金鑰可以登入而無需建立一個執行 `/permissions` 並開啟新的 [**Auto mode** 標籤](https://code.claude.com/docs/zh-TW/auto-mode-config.md#edit-rules-from-permissions)以檢視和編輯自動模式分類器規則，而無需開啟設定檔當自動模式可用時，Manual 和 `acceptEdits` 權限模式中的 Bash 權限提示會提供 [**是的，並切換到自動模式**](https://code.claude.com/docs/zh-TW/permission-modes.md#switch-permission-modes)選項；選擇它以核准命令並將工作階段切換到自動模式在您 [使用 `/cd` 移動工作階段](https://code.claude.com/docs/zh-TW/permissions#move-the-session-to-another-directory)後，新目錄的專案設定、hooks、`.mcp.json` 伺服器、skills 和子代理會立即生效，而不是在下一個 `--resume` 時生效在非互動式工作階段中，包括 `-p` 執行、Agent SDK 執行和雲端工作階段，Claude Code [繼續回應](https://code.claude.com/docs/zh-TW/errors.md#the-response-above-may-be-incomplete)伺服器錯誤、連線中斷或停滯中斷的回應，當部分回應包含文字且沒有工具呼叫時在其 `maxTurns` 限制處停止的子代理會傳回標記為部分的輸出，並提示 Claude 可以 [使用 `SendMessage` 繼續它](https://code.claude.com/docs/zh-TW/sub-agents#resume-subagents)，而不是顯示為已完成在 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上，同一機器上的工作階段現在可以 [彼此傳訊](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#availability)、`/loop` 可以 [選擇自己的間隔](https://code.claude.com/docs/zh-TW/scheduled-tasks.md#let-claude-choose-the-interval)，以及 `/model` 和 `/effort` 立即應用而不是在回合結束後應用原生安裝程式和自動更新程式下載 zstd 壓縮的組建，在 Linux x64 上約 75 MB 而不是 340 MB，原生組建按需載入程式碼，每個工作階段使用大約 40 到 70 MB 更少的記憶體

[v2.1.240–v2.1.250 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-240)

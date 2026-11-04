<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w26 | lastmod: 2026-09-09 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w26（官方 zh-TW，lastmod 2026-09-09）｜分類：What's New › What's New｜EN 摘要：Authenticate MCP servers from your shell with claude mcp login, get a response to shell mode command output with the ! prefix, and resume a conversation from before /clear with /rewind.

# 第 26 週 · 2026 年 6 月 22–26 日

> 使用 claude mcp login 從您的 shell 驗證 MCP 伺服器，使用 ! 前綴取得 shell 模式命令輸出的回應，以及使用 /rewind 從 /clear 之前恢復對話。

版本 [v2.1.185 → v2.1.193](https://code.claude.com/docs/en/changelog.md#2-1-185)
2 項功能 · 6 月 22–26 日

從 CLI 驗證 MCP 伺服器
v2.1.186

新的 `claude mcp login <name>` 和 `claude mcp logout <name>` 命令可從您的 shell 驗證已設定的 MCP 伺服器，而不是使用互動式 `/mcp` 選單。`claude mcp login` 直接執行伺服器的 OAuth 流程，而 `claude mcp logout` 會清除儲存的認證。

在不開啟工作階段的情況下執行已設定伺服器的 OAuth 流程：

```bash terminal theme={null}
claude mcp login sentry
```

[從命令列驗證](https://code.claude.com/docs/zh-TW/mcp.md#authenticate-from-the-command-line)

Shell 模式回應命令輸出
v2.1.186

您使用 `!` 前綴執行的命令現在會在輸出進入文字記錄後從 Claude 獲得回應，因此您可以執行 `! npm test` 並獲得失敗的說明，而無需第二個提示。回應成本與傳送一般提示相同。若要保持較早的行為（其中輸出被新增至內容而不獲得回應），請在 `settings.json` 中將 `respondToBashCommands` 設定為 `false`。

執行命令並取得其輸出的回應：

```text Claude Code theme={null}
> ! npm test
```

[使用 ! 前綴的 Shell 模式](https://code.claude.com/docs/zh-TW/interactive-mode.md#shell-mode-with-prefix)

其他改進

`/rewind` 現在可以從執行 `/clear` 之前恢復對話新的 `sandbox.credentials` 設定會阻止沙箱化命令讀取認證檔案和祕密環境變數組織設定的模型限制現在適用於模型選擇器、`--model`、`/model` 和 `ANTHROPIC_MODEL`，當選取受限制的模型時會顯示「受您組織的設定限制」訊息新的 `autoMode.classifyAllShell` 設定會將所有 Bash 和 PowerShell 命令路由通過自動模式分類器，拒絕原因現在會顯示在文字記錄、拒絕快顯通知和 `/permissions` 中新的 `claude_code.assistant_response` OpenTelemetry 日誌事件會攜帶模型的回應文字；已經記錄提示內容的部署在升級時會開始接收它，因此請設定 `OTEL_LOG_ASSISTANT_RESPONSES=0` 以僅保留提示背景子代理現在會在主工作階段中顯示權限提示，而不是自動拒絕；對話框會顯示哪個代理在詢問，而 Esc 只會拒絕該工具`/install-github-app` 現在可以僅安裝 GitHub App，並跳過 Actions 工作流程和祕密步驟您在沙箱網路權限對話框中允許的主機會在工作階段的其餘時間內被記住，而不是在每次連線時重新提示串流回應使用的 CPU 減少約 37%，而來自終端輸出快取的長工作階段記憶體成長已減少`/review <pr>` 現在使用與 `/code-review medium` 相同的審查引擎Bash 模式 `!` 命令獲得即時檔案路徑自動完成

[v2.1.185–v2.1.193 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-185)

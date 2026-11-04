<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w21 | lastmod: 2026-09-10 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w21（官方 zh-TW，lastmod 2026-09-10）｜分類：What's New › What's New｜EN 摘要：Use auto mode on the Pro plan and with Sonnet 4.6, see which skills, subagents, and MCP servers drive your plan limits in /usage, and review diffs with the new /code-review command.

# 第 21 週 · 2026 年 5 月 18–22 日

> 在 Pro 方案上使用 auto mode 並搭配 Sonnet 4.6，在 /usage 中查看哪些 skills、subagents 和 MCP servers 推動您的方案限制，並使用新的 /code-review 命令檢查差異。

Releases [v2.1.143 → v2.1.149](https://code.claude.com/docs/en/changelog.md#2-1-143)
1 feature · 5 月 18–22

Pro 方案上的 Auto mode
CLI

Auto mode 現已在 Pro 方案上提供，並支援 Sonnet 4.6 以及 Opus。它用背景安全檢查取代權限提示：常規操作無需中斷您即可執行，而破壞性或可疑的操作會被阻止並顯示。

更新 Claude Code，然後使用 Shift+Tab 切換模式；一旦您的帳戶符合要求，auto mode 就會出現在循環中：

```bash terminal theme={null}
claude update
```

該命令會列印 `Successfully updated` 以及新的版本號，或如果不需要更新則列印 `Claude Code is up to date`。一旦 auto mode 啟用，提示頁尾會顯示 `auto mode on`。

[Auto mode 要求](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)

其他亮點

[`/usage`](https://code.claude.com/docs/zh-TW/costs#track-your-costs) 現在顯示推動您方案限制的內容的按類別細分，將最近的使用情況歸因於 skills、subagents、plugins 和個別 MCP servers"Extra usage" 在整個 CLI 中重新命名為 "usage credits"，`/extra-usage` 現在是 `/usage-credits`。舊名稱仍然有效。該命令需要透過 `/login` 使用您的 claude.ai 訂閱登入，並且不適用於 API 金鑰驗證。新的 [`/code-review`](https://code.claude.com/docs/zh-TW/code-review) 命令在選定的努力級別（例如 `/code-review high`）報告正確性錯誤，`--comment` 將發現作為內聯 GitHub PR 評論發佈。`/simplify` 保留為單獨的清理專用檢查。背景會話現在在 `/resume` 中與互動式會話一起出現，標記為 `bg`，並且在 `claude agents` 中使用 `Ctrl+T` 固定的會話在空閒時保持活動`claude agents --json` 將實時會話列為 JSON 以供指令碼編寫，例如狀態欄和會話選擇器PowerShell tool 現在在 Windows 上預設為啟用，適用於 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 使用者；使用 `CLAUDE_CODE_USE_POWERSHELL_TOOL=0` 選擇退出`claude plugin disable` 現在在另一個啟用的 plugin 依賴於目標時拒絕，`claude plugin enable` 強制啟用傳遞依賴項`/plugin` marketplace 瀏覽窗格顯示預計的上下文成本，Discover 和 Browse 螢幕在安裝前列出 plugin 的命令、agents、skills、hooks 和 MCP/LSP servers新的 `worktree.bgIsolation: "none"` 設定讓背景會話直接編輯工作副本，無需 `EnterWorktree`，適用於 worktrees 不實用的儲存庫Markdown 輸出呈現 GFM 任務列表複選框，`/diff` 詳細檢視使用鍵盤滾動狀態行 JSON 輸入現在在偵測到時包含 GitHub 儲存庫和 PR 資訊Enterprise：`allowAllClaudeAiMcps` 受管設定在 `managed-mcp.json` 旁邊載入 claude.ai 雲端 MCP 連接器

[v2.1.143–v2.1.149 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-143)

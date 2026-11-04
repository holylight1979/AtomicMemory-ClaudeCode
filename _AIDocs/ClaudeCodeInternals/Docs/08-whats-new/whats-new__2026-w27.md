<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w27 | lastmod: 2026-09-10 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w27（官方 zh-TW，lastmod 2026-09-10）｜分類：What's New › What's New｜EN 摘要：Claude Sonnet 5 becomes the default model, Claude in Chrome reaches general availability, subagents run in the background by default, Claude Desktop arrives on Linux in beta, and /radio tunes into Claude FM.

# 第 27 週 · 6 月 29 日 – 7 月 3 日，2026 年

> Claude Sonnet 5 成為預設模型，Claude in Chrome 達到正式推出，子代理預設在背景執行，Claude Desktop 在 Linux 上推出測試版，/radio 調頻至 Claude FM。

Releases [v2.1.195 → v2.1.201](https://code.claude.com/docs/en/changelog.md#2-1-195)
5 項功能 · 6 月 29 日 – 7 月 3 日

Claude Sonnet 5
新模型

Sonnet 5 是 Pro、Team Standard 和 Enterprise 訂閱座位的新預設模型：以 Sonnet 定價提供頂級編碼和工具使用功能，具有原生 1M 代幣內容視窗和預設啟用的自適應思考。API 定價在 8 月 31 日前為促銷價格，每 MTok 為 \$2/\$10。需要 v2.1.197 或更新版本。

按名稱切換至 Sonnet 5，或從模型選擇器中選擇：

```text Claude Code theme={null}
> /model claude-sonnet-5
```

[模型配置](https://code.claude.com/docs/zh-TW/model-config.md#available-models)

Claude in Chrome 正式推出
v2.1.198

Chrome 整合已針對所有直接 Anthropic 方案的使用者結束預覽階段，正式推出。Claude Code 透過 Claude in Chrome 擴充功能驅動您的瀏覽器：它開啟標籤、點擊頁面、填寫表單、讀取主控台日誌，並共享您的登入狀態，因此它可以測試它建立的應用程式，而無需您切換內容。

[使用 Claude Code 搭配 Chrome](https://code.claude.com/docs/zh-TW/chrome.md)

子代理預設在背景執行
v2.1.198

Claude 現在在子代理執行時繼續工作，並在子代理完成時取得其結果，而不是暫停對話以等待。當 Claude 需要結果才能繼續時，它仍會在前景執行子代理，背景子代理會在您的主要工作階段中顯示每個權限提示。使用 `background` frontmatter 欄位固定子代理的行為。

[在前景或背景執行子代理](https://code.claude.com/docs/zh-TW/sub-agents.md#run-subagents-in-foreground-or-background)

Claude Desktop on Linux
Desktop

Claude 桌面應用程式現已在 Ubuntu 22.04+ 和 Debian 12+ 上以測試版形式提供，支援 x86\_64 和 arm64。您可以獲得與 macOS 和 Windows 相同的 Chat、Cowork 和 Claude Code 體驗：平行工作階段、視覺差異檢視、整合終端和編輯器，以及即時應用程式預覽。從 Anthropic 的 apt 儲存庫安裝，因此更新會透過定期套件更新進行。

[Claude Desktop on Linux](https://code.claude.com/docs/zh-TW/desktop-linux.md)

/radio
CLI

Claude FM 已開播。`/radio` 在您的瀏覽器中開啟 lo-fi 廣播串流，供您編碼時收聽，當沒有瀏覽器可用時會列印串流 URL。在 Amazon Bedrock、Google Cloud 的 Agent Platform 或 Microsoft Foundry 上不可用。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/x358isu_VzLnyTEN/images/whats-new/radio.mp4?fit=max&auto=format&n=x358isu_VzLnyTEN&q=85&s=36a0c33859cef119c7192dceea8bcbd3" />

從任何工作階段調頻：

```text Claude Code theme={null}
> /radio
```

[所有命令](https://code.claude.com/docs/zh-TW/commands.md#all-commands)

其他成果

[Artifacts](https://code.claude.com/docs/zh-TW/artifacts.md) 現已正式推出，並包含在 Pro 和 Max 方案中，加入 Team 和 Enterprise管理員可以在組織主控台中設定 [組織預設模型](https://code.claude.com/docs/zh-TW/model-config.md#organization-default-model)；當您尚未選擇模型時，它在 `/model` 中顯示為「組織預設」堆疊的技能叫用（例如 `/skill-a /skill-b do XYZ`）現在會載入所有前導技能（最多 5 個），而不僅是第一個`AskUserQuestion` 對話框預設不再自動繼續；透過 `/config` 選擇加入閒置逾時「預設」權限模式現在在 CLI、`--help`、VS Code 和 JetBrains 中命名為「Manual」；`--permission-mode manual` 與 `default` 一起被接受新的 `/dataviz` 技能提供圖表和儀表板設計指導，附帶可執行的調色盤驗證器內建的 Explore 代理現在繼承主要工作階段的模型（上限為 Opus），而不是在 Haiku 上執行從 `claude agents` 啟動的背景代理現在在 worktree 中完成程式碼工作時提交、推送並開啟草稿 PR，而不是停下來詢問您具有連字號識別符（例如 `code-reviewer`）的 Hook 匹配器現在進行精確匹配而不是子字串匹配；使用 `mcp__brave-search__.*` 來匹配來自連字號 MCP 伺服器的所有工具與您的使用限制無關的暫時伺服器速率限制錯誤現在會自動重試，並為訂閱者進行退避，而不是使轉換失敗串流閒置監視程式現在預設對所有提供者啟用：當回應串流在 5 分鐘內未產生任何事件時，它會中止並重試（`CLAUDE_ENABLE_STREAM_WATCHDOG=0` 以停用）

[v2.1.195–v2.1.201 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-195)

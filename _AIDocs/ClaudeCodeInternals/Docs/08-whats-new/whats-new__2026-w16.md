<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w16 | lastmod: 2026-09-09 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w16（官方 zh-TW，lastmod 2026-09-09）｜分類：What's New › What's New｜EN 摘要：Claude Opus 4.7 with the new xhigh effort level, Routines on Claude Code on the web, mobile push notifications that ping your phone when Claude needs you, a /usage breakdown that shows what's driving your limits, and native binaries replacing the bundled JavaScript.

# 第 16 週 · 2026 年 4 月 13–17 日

> Claude Opus 4.7 搭配新的 xhigh 努力等級、Claude Code 網頁版上的 Routines、行動推播通知在 Claude 需要您時 ping 您的手機、顯示限制驅動因素的 /usage 細目分析，以及取代捆綁 JavaScript 的原生二進位檔。

版本 [v2.1.105 → v2.1.113](https://code.claude.com/docs/en/changelog.md#2-1-105)
5 項功能 · 4 月 13–17 日

Claude Opus 4.7
新模型

Anthropic 最強大的編碼模型現在是 Max 和 Team Premium 的預設值，也可從 `/model` 在其他地方使用。它新增了一個 `xhigh` 努力等級，位於 `high` 和 `max` 之間：對大多數編碼和代理任務提供最佳結果，在您第一次切換到 4.7 時應用為預設值。`/effort` 現在在您不帶引數呼叫時會開啟互動式箭頭鍵滑塊，讓您可以在不記住等級名稱的情況下調整智能與速度。

一次切換模型和努力等級：

```text Claude Code theme={null}
> /model opus
> /effort xhigh
```

[模型配置：努力等級](https://code.claude.com/docs/zh-TW/model-config.md#adjust-effort-level)

Routines
web

範本化雲端代理，可按排程、GitHub 事件或 API 呼叫觸發。在 Claude Code 網頁版上定義一次 routine，包含提示、它可以接觸的儲存庫和所需的連接器，然後讓 PR 開啟、版本發佈或您自己的 webhook 在您的機器未執行時觸發它。觸發選擇器現在涵蓋具有選用篩選器的 GitHub 事件，並為每個 routine 提供一個令牌化的 `/fire` 端點供外部系統使用。

![在 Claude Code 網頁版上建立 routine，具有排程、GitHub 事件和 API 觸發器](https://mintcdn.com/claude-code/FTi4SBJ9YRs7d-5X/images/whats-new/routines.png?fit=max\&auto=format\&n=FTi4SBJ9YRs7d-5X\&q=85\&s=2ba818ea9280c549511cb48b9b4d1dc5)

從網頁 UI 建立一個，或從您的終端機搭建：

```text Claude Code theme={null}
> /schedule daily PR review at 9am
```

[Routines 指南](https://code.claude.com/docs/zh-TW/routines.md)

/usage 細目分析
CLI

更清楚地了解您的 Claude Code 使用量流向何處。`/usage` 現在顯示驅動您限制的因素：平行工作階段、子代理、快取遺漏和長上下文，每個都有您過去 24 小時的百分比和最佳化提示。按 `d` 或 `w` 在日檢視和週檢視之間切換。

![/usage 命令顯示對限制使用量有貢獻的細目分析](https://mintcdn.com/claude-code/FTi4SBJ9YRs7d-5X/images/whats-new/usage.png?fit=max\&auto=format\&n=FTi4SBJ9YRs7d-5X\&q=85\&s=792a4b43cbef4e2931974831f076bca6)

隨時執行：

```text Claude Code theme={null}
> /usage
```

[命令參考](https://code.claude.com/docs/zh-TW/commands.md)

行動推播通知
mobile

連接 [Remote Control](https://code.claude.com/docs/zh-TW/remote-control.md) 後，Claude 可以在長任務完成或需要決定以繼續進行時傳送推播通知到您的手機。在 `/config` 中使用「Claude 決定時推播」開啟它，或在您的提示中要求一個。當您啟動長代理執行並想離開終端機時很有用。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/uII1TETOZxBUZ3lB/images/whats-new/push-notifications.mp4?fit=max&auto=format&n=uII1TETOZxBUZ3lB&q=85&s=c91a967139596500cbdb581a53822ac1" />

要求 Claude 在完成時 ping 您：

```text Claude Code theme={null}
> notify me when the tests pass
```

[Remote Control：行動推播通知](https://code.claude.com/docs/zh-TW/remote-control.md#mobile-push-notifications)

原生二進位檔
v2.1.113

`claude` CLI 現在生成原生的每平台二進位檔，而不是捆綁的 JavaScript，因此已安裝的 `claude` 命令不再呼叫 Node。npm 套件透過選用相依性（例如 `@anthropic-ai/claude-code-darwin-arm64`）拉入正確的二進位檔，因此您的安裝命令不會改變。獨立安裝程式已經提供此二進位檔；npm 現在與其相符。

升級並檢查您正在執行的內容：

```bash theme={null}
claude update
claude --version
```

[設定指南](https://code.claude.com/docs/zh-TW/setup.md)

其他成果

新的 [`/ultrareview`](https://code.claude.com/docs/zh-TW/ultrareview)：使用平行多代理分析和對抗性批評傳遞在雲端進行全面程式碼審查。不帶引數執行以審查您目前的分支，或 `/ultrareview <PR#>` 審查特定 PR[自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)現在可供 Max 訂閱者在 Opus 4.7 上使用，`--enable-auto-mode` 旗標不再需要[工作階段摘要](https://code.claude.com/docs/zh-TW/interactive-mode.md#session-recap)顯示您離開時發生的一行摘要；按需執行 `/recap` 或從 `/config` 關閉它新的 `/tui` 命令和 `tui` 設定在對話中間切換經典和無閃爍渲染；焦點檢視從 `Ctrl+O` 移至其自己的 `/focus` 命令外掛程式可透過在工作階段開始或技能呼叫時自動啟用的頂層 `monitors` 資訊清單鍵來提供背景監視程式`/theme` 中的「自動（符合終端機）」選項遵循您終端機的深色/淺色模式`/fewer-permission-prompts` 掃描您的文字記錄以尋找常見的唯讀 Bash 和 MCP 呼叫，並為 `.claude/settings.json` 提議允許清單Claude 現在可以透過 Skill 工具發現並執行內建命令，例如 `/init`、`/review` 和 `/security-review``PreCompact` hooks 可以透過以代碼 2 結束或傳回 `{"decision":"block"}` 來阻止壓縮`ENABLE_PROMPT_CACHING_1H` 選擇 API 金鑰、Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 使用者進入 1 小時 prompt cache TTL`sandbox.network.deniedDomains` 設定從更廣泛的 `allowedDomains` 萬用字元中切割特定網域`/undo` 現在是 `/rewind` 的別名，`/proactive` 是 `/loop` 的別名強化的 Bash 權限：拒絕規則現在透過 `env`/`sudo`/`watch` 包裝器進行比對，`Bash(find:*)` 允許規則不再自動核准 `-exec` 或 `-delete`

[v2.1.105–v2.1.113 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-105)

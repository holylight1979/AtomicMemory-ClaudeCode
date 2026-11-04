<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w30 | lastmod: 2026-10-15 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w30（官方 zh-TW，lastmod 2026-10-15）｜分類：What's New › What's New｜EN 摘要：Opus 5 becomes the default Opus model, Claude Code Desktop adds an iOS Simulator pane, and the Claude Security plugin scans your code for vulnerabilities.

# 第 30 週 · 7 月 20–24 日，2026 年

> Opus 5 成為預設的 Opus 模型，Claude Code Desktop 新增 iOS Simulator 窗格，Claude Security plugin 掃描您的程式碼以尋找漏洞。

版本 [v2.1.214 → v2.1.219](https://code.claude.com/docs/en/changelog.md#2-1-214)
3 項功能 · 7 月 20–24 日

Claude Opus 5
新模型

Claude Opus 5 是 Claude Code 中新的預設 Opus 模型。它是 Max、Team Premium、Enterprise 隨用隨付以及 Anthropic API 上的預設模型，也是 AWS 上的 Claude Platform、Amazon Bedrock 和 Google Cloud 的 Agent Platform 上的預設模型。在 Anthropic API 以及 Max、Team 和 Enterprise 方案上，Opus 5 以 [1M 權杖內容視窗](https://code.claude.com/docs/zh-TW/model-config.md#extended-context)執行；在 Amazon Bedrock 和 Google Cloud 的 Agent Platform 上，請選擇 1M 模型變體。快速模式以每 MTok $10/$50 的價格移至 Opus 5。需要 v2.1.219 或更新版本。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/N3yEaTYPXMXFrF6k/images/whats-new/opus-5.mp4?fit=max&auto=format&n=N3yEaTYPXMXFrF6k&q=85&s=8536b1cb3180e539008f39930403e47b" />

按名稱切換至 Opus 5，或從模型選擇器中選擇：

```text Claude Code theme={null}
> /model claude-opus-5
```

[模型設定](https://code.claude.com/docs/zh-TW/model-config.md#available-models)

Claude Code Desktop 中的 iOS Simulator
Desktop

macOS 上的 Claude Code Desktop 獲得 iOS Simulator 窗格，在 Pro、Max 和 Team 方案上公開測試版。當 Claude 在模擬器中建置、啟動或檢查您的應用程式時，窗格會在對話旁邊開啟並即時串流裝置螢幕，因此您可以觀看 Claude 點選應用程式以驗證其變更，或自己驅動裝置。需要安裝 iOS 平台的 Xcode，以及 Claude Desktop v1.24012.0 或更新版本。

![Claude Code Desktop 顯示 iOS Simulator 窗格，在對話旁邊顯示 iPhone 應用程式](https://mintcdn.com/claude-code/N3yEaTYPXMXFrF6k/images/whats-new/ios-simulator.jpg?fit=max\&auto=format\&n=N3yEaTYPXMXFrF6k\&q=85\&s=6c88418ed14ed0fb12cc1af75b17f2ee)

要求 Claude 執行或測試您的應用程式，窗格會在應用程式啟動時開啟：

```text Claude Code theme={null}
> Build the app and run it in the simulator to check the onboarding flow.
```

[在模擬器中測試 iOS 應用程式](https://code.claude.com/docs/zh-TW/desktop-ios-simulator.md#run-your-app-in-the-simulator)

Claude Security plugin
plugin

Claude Security plugin 在 Claude Code 工作階段內執行您程式碼庫的多代理漏洞掃描：代理對應您的架構、建置威脅模型、搜尋漏洞，並在將報告寫入 `CLAUDE-SECURITY-<timestamp>/` 目錄之前獨立審查每項發現。掃描整個儲存庫或僅掃描分支的差異、提取請求或單一提交，然後將您選擇的發現轉換為已審查的修補程式，由您自己應用。

從官方 Anthropic marketplace 安裝 plugin，執行 `/reload-plugins`，然後使用 `/claude-security` 開始掃描：

```text Claude Code theme={null}
> /plugin install claude-security@claude-plugins-official
```

[掃描並修復您的程式碼庫](https://code.claude.com/docs/zh-TW/claude-security.md#scan-and-fix-your-codebase)

其他成果

[`/code-review`](https://code.claude.com/docs/zh-TW/code-review-local) 現在以具有自己上下文視窗的背景 subagent 身份執行，因此審查工作不會進入您的對話，發現會在完成時到達`/verify`、`/code-review` 和 `/deep-research` 僅在您叫用時執行；Claude 不再自行啟動它們[Emoji 快速代碼](https://code.claude.com/docs/zh-TW/interactive-mode.md#emoji-shortcodes)在提示詞輸入中自動完成：輸入 `:heart:` 以插入 emoji，或在 `:` 後輸入兩個或更多字元以獲得建議；使用 `emojiCompletionEnabled` 關閉它具有 `context: fork` 的 Skills [預設在背景執行](https://code.claude.com/docs/zh-TW/skills.md#run-skills-in-a-subagent)，而 skill 的 frontmatter 中的 `background: false` 會在同一回合中等待結果工作階段預設最多同時執行 20 個 subagent；使用 `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` 變更[限制](https://code.claude.com/docs/zh-TW/sub-agents.md#concurrent-subagent-limit)`--max-budget-usd` 現在對 subagent 強制執行上限：一旦支出達到上限，Claude 就無法啟動更多，執行中的背景 subagent 會停止新的 [`sandbox.filesystem.disabled`](https://code.claude.com/docs/zh-TW/sandboxing#disable-filesystem-isolation) 設定會跳過檔案系統隔離，同時保持網路出口控制在自動模式中，危險 `rm` 命令、背景工作和可疑 Windows 路徑的檢查不再開啟權限對話框；自動模式分類器會改為判決它們Bash 權限檢查在更多 shell 形式上失敗關閉，包括檔案描述符重新導向、`[[ ]]` 比較中的 Zsh 變數下標、可能執行不安全選項的 `help` 和 `man` 叫用，以及超過 10,000 個字元的命令[快速模式](https://code.claude.com/docs/zh-TW/fast-mode.md)不再支援 Opus 4.7：`/fast` 現在適用於 Opus 5 和 Opus 4.8長時間執行的工具呼叫會發出定期進度心跳，而不是保持沉默

[v2.1.214–v2.1.219 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-214)

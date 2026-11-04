<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w20 | lastmod: 2026-10-19 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w20（官方 zh-TW，lastmod 2026-10-19）｜分類：What's New › What's New｜EN 摘要：Manage every Claude Code session from one screen with agent view, keep Claude working toward a goal until a condition holds, and run fast mode on Opus 4.7 by default.

# 第 20 週 · 2026 年 5 月 11–15 日

> 從一個螢幕管理每個 Claude Code 工作階段，使用代理檢視，讓 Claude 持續朝著目標工作直到條件成立，並在 Opus 4.7 上預設執行快速模式。

版本 [v2.1.139 → v2.1.142](https://code.claude.com/docs/en/changelog.md#2-1-139)
3 項功能 · 5 月 11–15

Agent view
research preview

`claude agents` 為每個 Claude Code 工作階段開啟一個螢幕：什麼正在執行、什麼在等待您的輸入，以及什麼已完成。分派一個錯誤修復、一個拉取請求審查和一個不穩定測試調查作為三行，在另一個視窗中繼續工作，只在一行需要您時才介入。附加到任何一行以進入其完整對話，然後按 `←` 返回列表。每個背景工作階段在沒有終端連接的情況下繼續執行。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/ITvjicPxe1SM3GX7/images/whats-new/agent-view.mp4?fit=max&auto=format&n=ITvjicPxe1SM3GX7&q=85&s=0eefe6cbe75464c8f7902bba630ab7a4" />

從您的 shell 開啟儀表板：

```bash terminal theme={null}
claude agents
```

[Agent view](https://code.claude.com/docs/zh-TW/agent-view.md)

/goal
v2.1.139

設定完成條件，Claude 會在多個回合中持續朝著它工作，無需您提示每一步。在每個回合之後，一個快速模型檢查條件是否成立；如果不成立，Claude 會開始另一個回合，而不是將控制權交回。適用於具有可驗證終止狀態的大量工作，例如遷移模組直到每個呼叫位置都編譯並通過測試。目標在條件滿足後清除，並在互動、`-p` 和 Remote Control 中工作。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/ITvjicPxe1SM3GX7/images/whats-new/goal.mp4?fit=max&auto=format&n=ITvjicPxe1SM3GX7&q=85&s=6806df3780c548b93a02d6fa71da276b" />

設定目標並讓 Claude 執行直到它成立：

```text Claude Code theme={null}
> /goal all tests in test/auth pass and the lint step is clean
```

[Goals](https://code.claude.com/docs/zh-TW/goal.md)

Fast mode on Opus 4.7
research preview

`/fast` 現在預設在 Opus 4.7 上執行，而不是 Opus 4.6。快速模式是高速 Opus 配置：相同的模型品質，速度約快 2.5 倍，但每個 token 成本更高，適用於快速迭代和即時除錯。定價保持不變，為 $30/$150 per MTok，與 Opus 4.6 快速模式相同。要將快速模式固定到 Opus 4.6，請設定 `CLAUDE_CODE_OPUS_4_6_FAST_MODE_OVERRIDE=1`。

![Claude Code 模型選擇器顯示 Opus 4.7 Fast 1M 作為預設值，並啟用了 Fast 切換](https://mintcdn.com/claude-code/ITvjicPxe1SM3GX7/images/whats-new/fast-mode-opus-47.png?fit=max\&auto=format\&n=ITvjicPxe1SM3GX7\&q=85\&s=6b6d92f7748ce5328a1ee9a269fb1a87)

切換快速模式，現在在 Opus 4.7 上執行：

```text Claude Code theme={null}
> /fast
```

[Fast mode on Opus 4.7](https://code.claude.com/docs/zh-TW/fast-mode.md#understand-the-cost-tradeoff)

其他成果

`claude agents` 獲得了分派標誌（`--add-dir`、`--settings`、`--mcp-config`、`--plugin-dir`、`--permission-mode`、`--model`、`--effort`、`--dangerously-skip-permissions`）來配置背景工作階段，`claude agents --cwd <path>` 將工作階段列表限制在一個目錄新的 hook `args: string[]` exec 形式直接生成命令而不使用 shell，因此路徑佔位符永遠不需要引用新的 `continueOnBlock` 配置選項用於 `PostToolUse` hooks，將 hook 的拒絕原因反饋給 Claude 並繼續回合，而不是結束它hook JSON 輸出中的新 `terminalSequence` 欄位讓 hooks 發出桌面通知、視窗標題和鈴聲，無需控制終端Rewind 菜單新增了「在此處總結」以壓縮較早的上下文，同時保持最近的回合完整當設定 `ANTHROPIC_API_KEY`、`apiKeyHelper` 或 `ANTHROPIC_AUTH_TOKEN` 時，Remote Control、`/schedule`、claude.ai MCP 連接器和通知偏好設定現在被禁用，即使與 claude.ai 登入並行；取消設定 API 金鑰以使用這些功能MCP stdio 伺服器現在在其環境中接收 `CLAUDE_PROJECT_DIR`，與 hooks 相符，plugin 配置可以在命令中參考 `${CLAUDE_PROJECT_DIR}``claude plugin details <name>` 顯示 plugin 的元件清單和預計的每個工作階段 token 成本，`/plugin` 詳細資訊窗格現在也列出 plugin 提供的 LSP 伺服器具有根級 `SKILL.md` 且沒有 `skills/` 子目錄的 Plugins 現在被呈現為一個 skill`/feedback` 現在可以包含過去 24 小時或 7 天內的最近工作階段，用於跨越超過當前工作階段的問題Agent tool `subagent_type` 現在不區分大小寫和分隔符地匹配，因此 `"Code Reviewer"` 解析為 `code-reviewer`

[v2.1.139–v2.1.142 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-139)

<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w33 | lastmod: 2026-10-15 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w33（官方 zh-TW，lastmod 2026-10-15）｜分類：What's New › What's New｜EN 摘要：Claude Code Desktop auto-continues after a usage limit resets, fork mode turns on by default, and GitLab merge requests and marketplaces join GitHub.

# 第 33 週 · 2026 年 8 月 10–14 日

> Claude Code Desktop 在用量上限重設後自動繼續，Fork 模式預設開啟，GitLab 合併請求和市集加入 GitHub。

版本 [v2.1.225 → v2.1.233](https://code.claude.com/docs/en/changelog.md#2-1-225)
3 項功能 · 8 月 10–14 日

Desktop 上達到用量上限後自動繼續
Desktop

當您在 Claude Code Desktop 的 Code 分頁中達到工作階段限制時，限制卡片現在提供 **限制重設時自動繼續** 核取方塊。勾選它，Desktop 應用程式會在重設後重試中斷的回合。卡片會顯示重試時間。每週限制卡片不提供此選項。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/2SnAdpL4dJ18nKb3/images/whats-new/desktop-auto-continue.mp4?fit=max&auto=format&n=2SnAdpL4dJ18nKb3&q=85&s=1937f489695feaea715e48ecfd7e62cd" />

下次出現工作階段限制卡片時，勾選 **限制重設時自動繼續** 並保持工作階段開啟。卡片會顯示 `Auto-resuming at` 後面跟著重設時間，一旦限制重設，回合就會自動繼續。

[達到用量上限時該怎麼辦](https://code.claude.com/docs/zh-TW/errors.md#youve-hit-your-session-limit)

Fork 模式預設開啟
v2.1.232

Fork 模式現在在互動式工作階段中預設開啟。Claude 可以請求 `fork` subagent 類型，它繼承完整的對話和提示詞快取，而不是從頭開始，所以您不必為側邊任務重新解釋背景。Claude 在互動式工作階段中產生的 subagent（除了 agent team 隊友產生的 subagent 外）也預設在背景中執行。

使用需要您迄今為止討論的所有內容的任務自行啟動 fork：

```text Claude Code theme={null}
> /subtask draft unit tests for the parser changes so far
```

fork 會出現在您的提示詞下方的面板中，其結果在完成時會到達您的對話。若要關閉 fork 模式，請設定 `CLAUDE_CODE_FORK_SUBAGENT=0`。

[開啟或關閉 fork 模式](https://code.claude.com/docs/zh-TW/sub-agents.md#turn-fork-mode-on-or-off)

GitLab 合併請求和市集
v2.1.232

外掛程式市集複製裸 `gitlab.com` URL，包括巢狀子群組。在 v2.1.233 或更新版本上，將 GitLab 合併請求 URL 傳遞給 `--worktree` 以從中建立分支，`claude agents` 檢視會將連結到合併請求的工作階段標記為 `!N`。Claude Code 也會遮蔽 GitLab token 系列（例如 `glpat-` 和 `glrt-`），並以與保護 `gh` 相同的方式保護 `glab` CLI 的設定存放區。

在從合併請求建立分支的 worktree 中啟動工作階段：

```bash terminal theme={null}
claude --worktree https://gitlab.com/group/project/-/merge_requests/42
```

當 `origin` 在 gitlab.com 上時，Claude Code 會擷取 `merge-requests/42/head` 並在其自己的 worktree 中的該分支上開啟工作階段。

[從提取或合併請求建立 worktree 分支](https://code.claude.com/docs/zh-TW/worktrees.md#branch-from-a-pull-request)

其他成果

在提示詞中輸入 `@` 以[提及另一個 Claude 工作階段](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#message-another-session)的名稱，Claude 會使用 `SendMessage` 直接向其傳送訊息；完全符合一個即時工作階段的裸名稱現在無需確認步驟即可傳遞一台機器上的互動式工作階段保持[唯一名稱](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#see-which-sessions-claude-can-reach)：如果您使用另一個即時工作階段已使用的名稱啟動或重新命名工作階段，Claude Code 會為您的工作階段提供 `name-word-word` 變體並告知您外掛程式市集接受 [`command` 來源](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference#command-plugin-source)：本機命令會列印外掛程式目錄，Claude Code 會在每個工作階段中重新解析並應用，無需重新啟動在 Linux 和 WSL 上，將 [`CLAUDE_CODE_TOOL_MEMORY_LIMIT`](https://code.claude.com/docs/zh-TW/tools-reference#memory-limit-on-linux-and-wsl) 設定為 `4G` 之類的大小，以限制 Bash 和 PowerShell 工具命令可以使用的記憶體任務追蹤工具（例如 `TaskCreate`、`TaskUpdate` 和 `TodoWrite`）[在 Opus 4.8、Sonnet 5、Fable 5、Mythos 5 及更新版本的這些系列上不再可用](https://code.claude.com/docs/zh-TW/tools-reference.md#task-tool-availability)；設定 `CLAUDE_CODE_ENABLE_TODO_TOOLS=1` 以重新啟用它們[`/code-review`](https://code.claude.com/docs/zh-TW/code-review-local) 在高、超高和最大努力級別現在像其他級別一樣在背景 agent 中執行[`/plugin install plugin@marketplace`](https://code.claude.com/docs/zh-TW/plugins/install#install-a-plugin) 首先重新整理市集，因此新發佈的外掛程式無需手動市集更新即可安裝設定接受 [`additionalMarketplaces` 和 `allowedMarketplaces`](https://code.claude.com/docs/zh-TW/settings-reference#marketplace-key-aliases) 作為 `extraKnownMarketplaces` 和 `strictKnownMarketplaces` 的別名在較新的模型上，Claude 可以[使用 Write 工具覆寫現有檔案](https://code.claude.com/docs/zh-TW/tools-reference.md#write-tool-behavior)，無需在此工作階段中先讀取它，符合 Edit 工具的規則；較舊的模型需要讀取VS Code 擴充功能可以[將工作階段清單組織成群組](https://code.claude.com/docs/zh-TW/vs-code.md#organize-sessions-into-groups)：按右鍵以建立、重新命名或刪除群組，並使用 Cmd/Ctrl- 或 Shift-點擊以一次移動多個工作階段如果您的組織透過[具有支出限制的 Claude 應用程式閘道](https://code.claude.com/docs/zh-TW/claude-apps-gateway-spend-limits.md)路由 Claude Code，Claude Code 會在您達到限制時顯示限制期間、其重設時間和操作員的訊息

[v2.1.225–v2.1.233 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-225)

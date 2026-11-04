<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w22 | lastmod: 2026-09-10 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w22（官方 zh-TW，lastmod 2026-09-10）｜分類：What's New › What's New｜EN 摘要：Run Claude Code on Claude Opus 4.8, orchestrate large tasks with dynamic workflows, catch security issues with the security-guidance plugin, and use fast mode on Opus 4.8 at a lower price.

# 第 22 週 · 5 月 25–29 日，2026 年

> 在 Claude Opus 4.8 上執行 Claude Code、使用動態工作流程協調大型任務、使用 security-guidance 外掛程式捕捉安全問題，以及以更低的價格在 Opus 4.8 上使用快速模式。

版本 [v2.1.150 → v2.1.157](https://code.claude.com/docs/en/changelog.md#2-1-150)
4 項功能 · 5 月 25–29 日

Claude Opus 4.8
新模型

Opus 4.8 現在是 Max、Team Premium、Enterprise 隨用隨付和 Anthropic API 上的預設值。它預設為高努力；對於更難的任務，請使用 `/effort xhigh`。需要 v2.1.154 或更新版本。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/QsIrGXGFg6xd7joy/images/whats-new/opus-4-8.mp4?fit=max&auto=format&n=QsIrGXGFg6xd7joy&q=85&s=6ebcf5fe136467da2b254de1fe749ea7" />

按名稱切換到 Opus 4.8，或從模型選擇器中選擇它：

```text title="Claude Code" wrap theme={null}
/model claude-opus-4-8
```

[模型配置](https://code.claude.com/docs/zh-TW/model-config.md#available-models)

Dynamic workflows
研究預覽

工作流程是 Claude 為您的任務編寫的協調指令碼，並在背景中跨許多子代理執行。當任務對於一個對話來協調太大時，請使用一個：整個程式碼庫審計、大型遷移、需要交叉檢查的研究問題。使用 `/workflows` 管理執行。

![Claude Code on Opus 4.8 showing a Dynamic workflow requested indicator for a prompt that asks for a workflow to migrate every internal fetch() call](https://mintcdn.com/claude-code/QsIrGXGFg6xd7joy/images/whats-new/dynamic-workflows.png?fit=max\&auto=format\&n=QsIrGXGFg6xd7joy\&q=85\&s=26671fa8607cec3453ed9753f821bd4f)

描述任務並要求工作流程：

```text title="Claude Code" wrap theme={null}
create a workflow that migrates every internal fetch() call to the new HttpClient wrapper
```

[Dynamic workflows](https://code.claude.com/docs/zh-TW/workflows.md)

Security guidance plugin
plugin

security-guidance 外掛程式檢查 Claude 的程式碼變更是否存在漏洞，並在同一工作階段中修復它們。它在每次編輯時執行快速模式檢查，在每個回合結束時執行模型檢查，以及在提交或推送時執行更深入的代理檢查。在 `.claude/claude-security-guidance.md` 中新增專案規則。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/QsIrGXGFg6xd7joy/images/whats-new/security-guidance.mp4?fit=max&auto=format&n=QsIrGXGFg6xd7joy&q=85&s=c91d865936411586f42b24c558bcdd1d" />

從官方 Anthropic 市場安裝它：

```text title="Claude Code" wrap theme={null}
/plugin install security-guidance@claude-plugins-official
```

然後在目前工作階段中啟用它：

```text title="Claude Code" wrap theme={null}
/reload-plugins
```

[Security guidance plugin](https://code.claude.com/docs/zh-TW/security-guidance.md)

Fast mode on Opus 4.8
研究預覽

快速模式現在預設為 Opus 4.8，每 MTok 為 \$10/\$50：標準速率的 2 倍，速度約為 2.5 倍。Opus 4.7 和 4.6 保持在 \$30/\$150。Opus 4.6 快速模式已棄用。

切換快速模式，現在在 Opus 4.8 上：

```text title="Claude Code" wrap theme={null}
/fast
```

[快速模式定價](https://code.claude.com/docs/zh-TW/fast-mode.md#understand-the-cost-tradeoff)

其他成果

在 `claude agents` 中，在 shell 命令前加上 `!` 以將其作為背景工作執行，您可以附加到該工作並從中分離；也可用作 `claude --bg --exec 'pytest -x'`位於 `.claude/skills` 目錄中的外掛程式現在會自動載入，不需要市場，`claude plugin init <name>` 會為新外掛程式搭建框架新的 `/reload-skills` 命令重新掃描技能目錄而無需重新啟動，`SessionStart` hooks 可以傳回 `reloadSkills: true` 以使它們安裝的技能在同一工作階段中可用技能和命令可以在 frontmatter 中設定 `disallowed-tools` 以在技能處於活動狀態時從模型中移除工具新的 `MessageDisplay` hook 事件讓 hooks 在顯示助手訊息文字時轉換或隱藏它Claude Code 現在在找不到主要模型時會切換到您配置的 `--fallback-model` 以進行工作階段的其餘部分，而不是使每個請求都失敗外掛程式可以在 `plugin.json` 或市場項目中宣告 `defaultEnabled: false`，以便它們安裝而不開啟，直到您啟用它們Vim 模式：在 NORMAL 模式下按 `/` 開啟反向歷史搜尋，與 Bash 和 Zsh vi-mode 相符串流工具執行現在始終啟用，包括在禁用遙測和 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上`←←` 開啟代理檢視現在適用於 Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry 和禁用遙測的情況Chrome 中的 Claude：透過 `/chrome` → "選擇瀏覽器…" 選擇要使用的連接瀏覽器，或在瀏覽器操作執行時在聊天中選擇多個連接的瀏覽器`claude mcp list` 和 `claude mcp get` 現在將未批准的 `.mcp.json` 伺服器顯示為待批准，而不是在輸出被管道傳輸時自動批准和連接

[v2.1.150–v2.1.157 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-150)

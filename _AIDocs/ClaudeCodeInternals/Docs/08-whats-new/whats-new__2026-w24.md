<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w24 | lastmod: 2026-09-10 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w24（官方 zh-TW，lastmod 2026-09-10）｜分類：What's New › What's New｜EN 摘要：Move a session to a new directory with /cd, let subagents spawn their own subagents, and troubleshoot a broken configuration with safe mode.

# 第 24 週 · 2026 年 6 月 8–12 日

> 使用 /cd 將工作階段移至新目錄、讓子代理程式產生自己的子代理程式，以及使用安全模式對損壞的設定進行故障排除。

版本 [v2.1.166 → v2.1.176](https://code.claude.com/docs/en/changelog.md#2-1-166)
3 項功能 · 6 月 8–12 日

使用 /cd 移動工作階段
v2.1.169

新的 `/cd` 命令將目前的工作階段移至不同的工作目錄，而不需重建提示快取：新目錄的 `CLAUDE.md` 會作為訊息附加，而不是取代系統提示。工作階段會重新定位到新目錄的專案儲存空間，因此 `--resume` 和 `--continue` 會在該處找到它。如果您之前未在該目錄中工作過，Claude 會提示您信任該目錄。

將工作階段移至另一個專案而不重新啟動：

```text Claude Code theme={null}
> /cd ../other-project
```

[命令參考](https://code.claude.com/docs/zh-TW/commands.md#all-commands)

子代理程式可以產生子代理程式
v2.1.172

子代理程式現在可以產生自己的子代理程式。提示下方的子代理程式面板顯示完整的樹狀結構：每一列都會顯示其後代的計數以及返回 `main` 的路徑。子代理程式鏈的深度上限為五層，以防止失控的並行樹狀結構。

開啟代理程式檢視以觀看工作展開時的巢狀樹狀結構：

```text Claude Code theme={null}
> /agents
```

[產生巢狀子代理程式](https://code.claude.com/docs/zh-TW/sub-agents.md#let-subagents-spawn-their-own-subagents)

使用安全模式進行故障排除
v2.1.169

使用 `--safe-mode` 啟動 Claude Code，或設定 `CLAUDE_CODE_SAFE_MODE`，以在停用所有自訂項目的情況下啟動：`CLAUDE.md`、skills、plugins、hooks、MCP 伺服器以及自訂命令和代理程式不會載入。驗證、模型選擇、內建工具和權限仍然有效。如果問題在安全模式中消失，則其中一個介面是原因。

啟動乾淨的工作階段以隔離損壞的設定：

```bash terminal theme={null}
claude --safe-mode
```

[針對乾淨的設定進行測試](https://code.claude.com/docs/zh-TW/debug-your-config.md#test-against-a-clean-configuration)

其他成果

[`fallbackModel`](https://code.claude.com/docs/zh-TW/model-config#fallback-model-chains) 設定最多三個備用模型，在主要模型過載或無法使用時按順序嘗試，而 `--fallback-model` 現在也適用於互動式工作階段工作階段標題現在以您的對話語言生成；使用 `language` 設定釘選特定的標題`claude agents --json` 新增 `--all` 以包含已完成的工作階段以及新的 `id` 和 `state` 欄位，並且不再省略被阻止或新分派的工作階段在 `/plugin` 中瀏覽市集的 plugins 現在有搜尋列新的 `disableBundledSkills` 設定和 `CLAUDE_CODE_DISABLE_BUNDLED_SKILLS` 隱藏捆綁的 skills、工作流程和內建命令不讓模型看到拒絕規則在工具名稱位置接受 glob，因此 `"*"` 拒絕所有工具，而拒絕規則中的未知工具名稱現在會在啟動時發出警告代理程式訊息傳遞已強化：透過 `SendMessage` 從其他代理程式轉送的訊息不再帶有使用者授權，而自動模式會阻止它們Amazon Bedrock 在 `AWS_REGION` 未設定時從 `~/.aws` 設定檔讀取 AWS 區域，而 `/status` 顯示區域的來源新的 `enforceAvailableModels` 受管設定使 `availableModels` 允許清單也限制預設模型Chrome 瀏覽器工具中的 Claude 現在在單一批次呼叫中載入，而不是每個工具一次`claude update` 在下載前宣佈目標版本，而不是保持沉默新的 `footerLinksRegexes` 設定將正規表達式相符的連結徽章新增至頁尾列

[v2.1.166–v2.1.176 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-166)

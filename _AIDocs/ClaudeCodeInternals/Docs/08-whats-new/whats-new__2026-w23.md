<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w23 | lastmod: 2026-09-25 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w23（官方 zh-TW，lastmod 2026-09-25）｜分類：What's New › What's New｜EN 摘要：Run auto mode on Amazon Bedrock, Google Cloud's Agent Platform, and Microsoft Foundry, prompt before writing files that can run code in acceptEdits mode, list installed plugins with /plugin list, and require an approved version range for managed deployments.

# 第 23 週 · 2026 年 6 月 1–5 日

> 在 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上執行自動模式，在 acceptEdits 模式下提示寫入可執行程式碼的檔案，使用 /plugin list 列出已安裝的外掛程式，以及為受管部署要求已核准的版本範圍。

發行版本 [v2.1.158 → v2.1.165](https://code.claude.com/docs/en/changelog.md#2-1-158)
4 項功能 · 6 月 1–5 日

Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上的自動模式
v2.1.158

自動模式現已在 Amazon Bedrock、Google Cloud 的 Agent Platform 和 Microsoft Foundry 上提供，適用於 Opus 4.7 和 Opus 4.8，以第三方提供者的背景安全檢查取代權限提示。透過設定 `CLAUDE_CODE_ENABLE_AUTO_MODE=1` 來選擇加入。

在第三方提供者上選擇加入，然後使用 Shift+Tab 切換到自動模式：

```bash terminal theme={null}
export CLAUDE_CODE_ENABLE_AUTO_MODE=1
```

[在第三方提供者上啟用自動模式](https://code.claude.com/docs/zh-TW/permission-modes.md#enable-auto-mode-on-bedrock-agent-platform-or-foundry)

更安全的自動編輯
v2.1.160

Claude Code 現在會在寫入可執行程式碼的檔案前提示，即使在 `acceptEdits` 模式下也是如此。受保護的集合涵蓋 shell 啟動檔案（例如 `.zshenv` 和 `.bash_login`）、`~/.config/git/` 下的 git 設定，以及建置工具設定（例如 `.npmrc`、`.bazelrc` 和 `.pre-commit-config.yaml`）。除了 `bypassPermissions` 模式外，這些寫入在任何模式下都不會自動核准。

在 acceptEdits 模式下工作；Claude 現在會在寫入這些檔案前暫停：

```bash terminal theme={null}
claude --permission-mode acceptEdits
```

[受保護的路徑](https://code.claude.com/docs/zh-TW/permission-modes.md#protected-paths)

使用 /plugin list 列出已安裝的外掛程式
v2.1.163

新的 `/plugin list` 命令會內聯列印已安裝的外掛程式，無需開啟 `/plugin` 選單，也可從 shell 中以 `claude plugin list` 的形式使用。在互動形式中，新增 `--enabled` 或 `--disabled` 以僅顯示處於該狀態的外掛程式。

列出目前開啟的外掛程式：

```text Claude Code theme={null}
> /plugin list --enabled
```

[外掛程式命令](https://code.claude.com/docs/zh-TW/plugins/cli-reference.md#plugin-list)

受管部署的版本要求
v2.1.163

兩個受管設定 `requiredMinimumVersion` 和 `requiredMaximumVersion` 可讓您的組織要求已核准的 Claude Code 版本範圍。超出範圍的用戶端會在啟動時退出，並告知使用者透過組織的方法進行更新。`claude update`、`claude install` 和 `claude doctor` 會繼續運作，以便使用者仍可復原。

在受管設定中新增下限，以便較舊的用戶端拒絕啟動：

```json managed-settings.json theme={null}
{
  "requiredMinimumVersion": "2.1.163"
}
```

[決定要強制執行的項目](https://code.claude.com/docs/zh-TW/admin-setup.md#decide-what-to-enforce)

其他成果

[動態工作流程](https://code.claude.com/docs/zh-TW/workflows.md)的觸發關鍵字從 `workflow` 變更為 `ultracode`；用您自己的話要求工作流程仍然有效，且關鍵字在提示中以紫色突出顯示[Stop 和 SubagentStop hooks](https://code.claude.com/docs/zh-TW/hooks.md) 可以傳回 `hookSpecificOutput.additionalContext` 以向 Claude 提供回饋並保持回合進行，而不是被視為錯誤`claude mcp` list、get 和 add 不再列印機密：環境變數參考不會展開，認證標頭和 URL 機密會被編輯平行工具批次中失敗的 Bash 命令不再取消其他命令；每個工具獨立傳回自己的結果當您使用單一檔案 `grep`、`egrep` 或 `fgrep` 檢視檔案時，編輯檔案不再需要先進行單獨的 Read在自動完成選單中按一下命令現在會將其填入您的提示中，而不是立即執行；按 Enter 鍵執行在 `--tools` 中列出 `Grep` 或 `Glob` 現在會在具有嵌入式搜尋的原生組建上提供專用搜尋工具，而不是無聲地忽略這些名稱`/effort` 現在會確認您選擇的等級是否會保留為新工作階段的預設值`OTEL_RESOURCE_ATTRIBUTES` 值現在會作為標籤附加到度量資料點上，因此您可以按自訂維度（例如團隊或儲存庫）切割使用量度量Windsurf 在 `/ide`、`/terminal-setup` 和 `/scroll-speed` 中重新命名為 Devin Desktop，遵循編輯器的重新品牌化`/btw` 獲得 `c to copy` 快捷鍵，可將原始 markdown 答案複製到剪貼簿

[v2.1.158–v2.1.165 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-158)

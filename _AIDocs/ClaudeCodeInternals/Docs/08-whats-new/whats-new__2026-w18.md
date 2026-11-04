<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w18 | lastmod: 2026-09-10 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w18（官方 zh-TW，lastmod 2026-09-10）｜分類：What's New › What's New｜EN 摘要：Claude Code on Windows runs without Git Bash, claude auth login accepts a pasted OAuth code when the browser callback can't reach localhost, claude project purge cleans up local state per project, and pasting a PR URL into /resume finds the session that created it.

# 第 18 週 · 4 月 27 日 – 5 月 1 日，2026 年

> Claude Code 在 Windows 上無需 Git Bash 即可運行，claude auth login 在瀏覽器回調無法到達 localhost 時接受貼上的 OAuth 代碼，claude project purge 清理每個專案的本地狀態，將 PR URL 貼到 /resume 中可找到建立該會話的會話。

Releases [v2.1.120 → v2.1.126](https://code.claude.com/docs/en/changelog.md#2-1-120)
4 個功能 · 4 月 27 日 – 5 月 1 日

無需瀏覽器回調即可登入
v2.1.126

`claude auth login` 現在在瀏覽器回調無法到達 localhost 時接受直接貼到終端機的 OAuth 代碼。這涵蓋了 WSL2、SSH 會話和容器，其中重新導向到本地連接埠不起作用。同一版本也修復了在緩慢或代理連接以及僅限 IPv6 的 devcontainers 上的登入逾時問題。

登入，然後貼上來自瀏覽器的代碼：

```bash theme={null}
claude auth login
```

[CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md#cli-commands)

claude project purge
v2.1.124

刪除專案的所有 Claude Code 狀態：文字記錄、任務、檔案歷史記錄和專案的設定項目。支援 `--dry-run` 預覽、`-y`/`--yes` 跳過確認、`-i`/`--interactive` 選擇，以及 `--all` 清理每個專案。

預覽將移除的內容：

```bash theme={null}
claude project purge --dry-run
```

然後真正執行：

```bash theme={null}
claude project purge
```

[CLI 參考](https://code.claude.com/docs/zh-TW/cli-reference.md)

按 PR URL 繼續
v2.1.122

當您使用 `gh pr create` 建立提取請求時，Claude Code 會將其連結到產生該請求的會話。現在您可以僅從 PR URL 返回該會話，無需記住其名稱。

開啟會話選擇器：

```text Claude Code theme={null}
> /resume
```

將 PR URL 貼到選擇器中。貼上的第一個字元會讓您進入搜尋模式，列表會篩選到建立該 PR 的會話。按 Enter 鍵繼續該會話。GitHub、GitHub Enterprise、GitLab 和 Bitbucket 提取和合併請求 URL 都可以使用。

```text Claude Code theme={null}
https://github.com/your-org/your-repo/pull/1234
```

若要開啟已篩選到 PR 的選擇器，請改為在命令列上傳遞 PR 編號：

```bash theme={null}
claude --from-pr 1234
```

[會話：使用會話選擇器](https://code.claude.com/docs/zh-TW/sessions.md#use-the-session-picker)

Windows 無需 Git Bash
Windows

不再需要 Git for Windows。當 Bash 不存在時，Claude Code 使用 PowerShell 作為 shell 工具，當啟用 PowerShell 工具時，它被視為主要 shell。現在會自動偵測透過 Microsoft Store、MSI 不含 PATH 或 `.NET` 全域工具安裝的 PowerShell 7。

[設定指南](https://code.claude.com/docs/zh-TW/setup.md)

其他成就

MCP 伺服器可以在其設定中使用 `alwaysLoad: true` 選擇退出工具搜尋延遲，以便該伺服器的所有工具始終可用新的 `claude plugin prune` 移除孤立的自動安裝外掛程式相依性，`plugin uninstall --prune` 級聯`/skills` 現在有一個類型篩選搜尋框，因此您可以在長列表中找到技能而無需捲動`PostToolUse` hooks 可以透過 `hookSpecificOutput.updatedToolOutput` 替換任何工具的工具輸出，不僅限於 MCP 工具新的 [`claude ultrareview`](https://code.claude.com/docs/zh-TW/ultrareview) 子命令從 CI 或指令碼非互動地執行 `/ultrareview`：將發現列印到 stdout（`--json` 用於原始輸出）並在完成時退出 0 或失敗時退出 1`--dangerously-skip-permissions` 現在繞過對 `.claude/`、`.git/`、`.vscode/`、shell 設定檔和其他先前受保護路徑的寫入提示，同時災難性移除命令仍會提示作為安全網當 `ANTHROPIC_BASE_URL` 指向 Anthropic 相容閘道時，`/model` 選擇器可以列出來自您閘道的 `/v1/models` 端點的模型；自 v2.1.129 起使用 `CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY=1` 選擇加入在啟動期間遇到暫時性錯誤的 MCP 伺服器現在會自動重試最多 3 次，而不是保持斷開連接`ANTHROPIC_BEDROCK_SERVICE_TIER` 選擇 Amazon Bedrock 服務層：`default`、`flex` 或 `priority``/terminal-setup` 啟用 iTerm2 的剪貼簿存取設定，以便 `/copy` 可以運作，包括從 tmuxGoogle Cloud 的 Agent Platform 現在支援 X.509 憑證型工作負載身分識別聯盟 (mTLS ADC)重大記憶體洩漏修復：影像繁重的會話、大型文字記錄歷史上的 `/usage` 以及沒有進度事件的長時間執行工具

[v2.1.120–v2.1.126 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-120)

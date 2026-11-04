<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w19 | lastmod: 2026-09-25 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w19（官方 zh-TW，lastmod 2026-09-25）｜分類：What's New › What's New｜EN 摘要：Load plugins from .zip archives and URLs, search command history across every project with Ctrl+R, branch new worktrees from local HEAD or the remote default, and block actions unconditionally with auto mode hard deny rules.

# 第 19 週 · 2026 年 5 月 4–8 日

> 從 .zip 檔案和 URL 載入 plugins，使用 Ctrl+R 搜尋所有專案的命令歷史記錄，從本機 HEAD 或遠端預設分支建立新 worktrees，以及使用 auto mode hard deny 規則無條件地阻止操作。

Releases [v2.1.128 → v2.1.136](https://code.claude.com/docs/en/changelog.md#2-1-128)
2 features · 5 月 4–8 日

從 .zip 檔案和 URL 載入 Plugins

`--plugin-dir` 現在除了接受目錄外，還接受 `.zip` plugin 檔案，新的 `--plugin-url` 旗標可在目前工作階段從 URL 取得 plugin 檔案。適合在將 plugin 新增至 marketplace 之前試用，或從成品存放區發送內部 plugins。

直接從 URL 載入 plugin：

```bash terminal theme={null}
claude --plugin-url https://example.com/my-plugin.zip
```

[Plugins 指南](https://code.claude.com/docs/zh-TW/plugins/overview.md)

在所有專案中搜尋歷史記錄
v2.1.129

`Ctrl+R` 反向搜尋現在預設搜尋所有專案中的所有提示，恢復了 v2.1.124 之前的行為。搜尋時按 `Ctrl+S` 可縮小範圍至目前專案或工作階段。當您記得上週在另一個 repo 中執行的命令，但不想費力尋找時，這非常方便。

[Interactive mode：命令歷史記錄](https://code.claude.com/docs/zh-TW/interactive-mode.md#command-history)

其他改進

新的 `worktree.baseRef` 設定（`fresh` | `head`）控制 `--worktree`、`EnterWorktree` tool 和 agent-isolation worktrees 是從遠端預設分支還是本機 `HEAD` 建立分支；預設的 `fresh` 會將未推送的提交排除在新 worktrees 之外新的 `settings.autoMode.hard_deny` 規則無條件地在 auto mode 中阻止符合條件的操作，無論允許例外如何，適用於即使套用更廣泛的允許規則也不應自動執行的操作Hooks 現在透過 `effort.level` JSON 輸入欄位和 `$CLAUDE_EFFORT` 環境變數接收作用中的努力等級，Bash tool 命令可以讀取 `$CLAUDE_EFFORT``CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN=1` 選擇退出全螢幕替代螢幕渲染器，並將對話保留在終端機的原生 scrollback 中`CLAUDE_CODE_PACKAGE_MANAGER_AUTO_UPDATE` 允許 Homebrew 或 WinGet 安裝在背景中執行升級並提示重新啟動`CLAUDE_CODE_SESSION_ID` 現在位於 Bash tool 子程序環境中，與傳遞給 hooks 的 `session_id` 相符`/mcp` 現在顯示已連線伺服器的 tool 計數，並標記以 0 個 tools 連線的伺服器`--channels` 現在適用於 console（API 金鑰）驗證Bash、hooks、MCP 和 LSP 等子程序不再繼承 `OTEL_*` 環境變數，因此透過 Bash tool 執行的 OTEL 檢測應用程式不再會採用 CLI 自身的 OTLP 端點Sub-agent 進度摘要現在會命中 prompt cache，將 `cache_creation` token 成本降低約 3 倍多項 OAuth 和認證可靠性修正：平行工作階段不再在重新整理 token 競爭後卡在 401，MCP OAuth 重新整理 tokens 在多個伺服器並行重新整理時不再遺失，並修正了來自並行認證寫入的罕見登入迴圈新的 `parentSettingsBehavior` 管理員金鑰讓管理員可以選擇將 SDK `managedSettings` 納入原則合併

[v2.1.128–v2.1.136 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-128)

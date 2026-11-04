<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w32 | lastmod: 2026-10-15 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w32（官方 zh-TW，lastmod 2026-10-15）｜分類：What's New › What's New｜EN 摘要：Claude Code sessions message each other, self-hosted environments run cloud sessions on your infrastructure, and auto mode becomes the default permission mode.

# 第 32 週 · 2026 年 8 月 3–7 日

> Claude Code 工作階段可以互相傳送訊息、自託管環境在您的基礎設施上執行雲端工作階段，以及自動模式成為預設權限模式。

版本 [v2.1.220 → v2.1.224](https://code.claude.com/docs/en/changelog.md#2-1-220)
3 項功能 · 8 月 3–7 日

跨工作階段傳訊
v2.1.224

您的 Claude Code 工作階段現在可以互相傳送訊息。Claude 使用 `ListAgents` 工具發現您的其他工作階段，並使用 `SendMessage` 傳送訊息，可以在您要求時傳送，也可以自動傳送，例如在一個工作階段中的變更影響另一個工作階段的工作時。訊息是 Claude 為另一個工作階段撰寫的文字，絕不是您的對話歷史記錄或檔案。適用於 macOS 和 Linux。需要 v2.1.224 或更新版本。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/N3yEaTYPXMXFrF6k/images/whats-new/cross-session-messaging.mp4?fit=max&auto=format&n=N3yEaTYPXMXFrF6k&q=85&s=8f33c3390f78660a4a26dc980f46159f" />

在同一台機器上開啟兩個工作階段，要求其中一個傳遞一些內容：

```text title="Claude Code" wrap theme={null}
Tell the session working on the payments API that users.name is now users.display_name
```

一旦 Claude 讀取訊息，另一個工作階段會顯示 `Message from` 列；按 `Ctrl+O` 展開它。若要查看 Claude 可以到達哪些工作階段，請執行 `/list-agents`。

[傳訊給另一個工作階段](https://code.claude.com/docs/zh-TW/cross-session-messaging.md#message-another-session)

自託管環境
v2.1.224

自託管環境在您組織自己的基礎設施上執行 Claude Code 雲端工作階段，在 Team 和 Enterprise 方案上處於公開測試版。在您的機器或容器上執行 `claude self-hosted-runner` 將它們轉變為執行器。當有人在從 claude.ai、行動或桌面應用程式或 `claude --cloud` 啟動工作階段時選擇您的環境，該工作階段會在您的網路內執行，可以存取您的內部服務。擁有者首先在 [管理設定](https://claude.ai/admin-settings/cloud-environments)中開啟 **允許自託管環境**。

![自託管環境管理頁面，列出環境（例如 linux-dev 和 macos-prod）及其狀態和活躍工作階段計數](https://mintcdn.com/claude-code/N3yEaTYPXMXFrF6k/images/whats-new/self-hosted-environments.jpg?fit=max\&auto=format\&n=N3yEaTYPXMXFrF6k\&q=85\&s=ae9152cb1670c8af517d1aee57689b14)

以擁有者身份登入，執行引導式設定，它會引導您建立環境並啟動執行器：

```bash terminal theme={null}
claude self-hosted-runner setup
```

執行器註冊後，環境在管理設定中顯示 **健康**。

[自託管環境快速入門](https://code.claude.com/docs/zh-TW/self-hosted-environments-quickstart.md#set-up-an-environment-and-runner)

自動模式成為預設
CLI

從 8 月 14 日開始，自動模式是 Pro、Max 和 Team 方案上新工作階段的預設權限模式。如果您自己設定了預設模式，它會保持不變，除非您接受一次性切換提示，而您的組織管理的預設模式不會改變。您仍然可以隨時切換模式。已在這些方案上生效：自動模式進行的分類器呼叫不再計入您的使用限制。

在切換前讓每個工作階段都以自動模式啟動，請在您的使用者設定中將其設定為預設值：

```json ~/.claude/settings.json {3} theme={null}
{
  "permissions": {
    "defaultMode": "auto"
  }
}
```

新工作階段隨後在狀態列中顯示 `auto mode on`。

[自動模式需求和控制](https://code.claude.com/docs/zh-TW/permission-modes.md#eliminate-prompts-with-auto-mode)

其他改進

VS Code 擴充功能獲得 [焦點檢視](https://code.claude.com/docs/zh-TW/vs-code.md#extension-settings)，它將每個回合的工具活動隱藏在一個可展開的列後面；從命令選單或使用 `Ctrl+Alt+F`（Mac 上為 `Ctrl+Option+F`）切換它沙箱憑證檔案在 Linux 和 WSL2 上接受 [`mode: "mask"`](https://code.claude.com/docs/zh-TW/sandboxing#mask-credential-files)，因此沙箱化命令讀取哨兵副本，而沙箱代理伺服器在出口時替換實際值；憑證遮罩也獲得 `extract`、JWT 感知 `decode` 和 AWS SigV4 重新簽署選項市集可以使用新的 `archive` 來源將外掛分發為 [zip 封存](https://code.claude.com/docs/zh-TW/plugins/marketplace-reference.md#archive-plugin-source)，透過 HTTPS 下載並具有可選的 SHA-256 釘選，因此安裝無需 git 或 npm`/review` 現在是 [`/code-review`](https://code.claude.com/docs/zh-TW/code-review-local) 的別名，`/code-review` 沒有 effort 等級時會重複使用您上次輸入的等級您使用 [`/fork`](https://code.claude.com/docs/zh-TW/agent-view#copy-the-session-with-%2Ffork) 複製的工作階段現在在其自己的 worktree 中進行程式碼變更，而不是原始工作階段的簽出您從 [`/plugin`](https://code.claude.com/docs/zh-TW/plugins/install#install-a-plugin) 安裝的外掛在當前工作階段中啟動（如果安全的話）；安裝摘要報告 `Plugin is now active.` 或告訴您執行 `/reload-plugins`[背景工作階段](https://code.claude.com/docs/zh-TW/agent-view.md#how-file-edits-are-isolated)在 worktree 中變更程式碼現在在完成前提交並推送，僅在任務要求時開啟草稿 pull request，並遵循您 `CLAUDE.md` 中的 git 指示每個工作階段 200 個 subagent 的上限已移除，因此長時間執行的工作階段不再拒絕新的 subagent；[並行](https://code.claude.com/docs/zh-TW/sub-agents.md#concurrent-subagent-limit)和深度限制仍然適用儲存庫的簽入設定不再能開啟 [Remote Control 自動連線](https://code.claude.com/docs/zh-TW/remote-control.md#enable-remote-control-for-all-sessions)；改為在您的使用者或受管設定中設定 `remoteControlAtStartup`，而專案和本機設定只能將其關閉[Worktree 隔離](https://code.claude.com/docs/zh-TW/worktrees.md#how-claude-code-enforces-isolation)現在不僅阻止檔案編輯，還阻止 Bash 命令和 git 重新導向到達主簽出，在每個工作階段類型和工作階段的 subagent 中Bash 命令不再能隱藏自身的一部分免於權限檢查，而製表符或不可見的 Unicode 填充不再隱藏命令的一部分免於核准對話框PreToolUse 自動允許 hook 不再在 Claude Code 的內部側任務（例如摘要和壓縮）中繞過工具限制[Ultraplan](https://code.claude.com/docs/zh-TW/ultraplan) 研究預覽已移除，包括 `/ultraplan` 命令和 `ultraplan` 關鍵字；改為使用 plan mode 或網路上的 Claude Code

[v2.1.220–v2.1.224 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-220)

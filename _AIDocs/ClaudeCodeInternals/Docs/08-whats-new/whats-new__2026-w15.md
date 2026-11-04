<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w15 | lastmod: 2026-09-10 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w15（官方 zh-TW，lastmod 2026-09-10）｜分類：What's New › What's New｜EN 摘要：Ultraplan cloud planning, the Monitor tool with self-pacing /loop, /team-onboarding for packaging your setup, and /autofix-pr from your terminal.

# 第 15 週 · 2026 年 4 月 6–10 日

> Ultraplan 雲端規劃、具有自我調整 /loop 的 Monitor 工具、用於打包設定的 /team-onboarding，以及從終端執行的 /autofix-pr。

版本 [v2.1.92 → v2.1.101](https://code.claude.com/docs/en/changelog.md#2-1-92)
4 項功能 · 4 月 6–10 日

Ultraplan
研究預覽

從終端在雲端啟動規劃模式，然後在瀏覽器中檢視結果。Claude 在網頁工作階段的 Claude Code 中起草計畫，同時您的終端保持空閒；當準備好時，您可以對各個部分進行評論、要求修訂，並選擇遠端執行或將其發送回 CLI。從 v2.1.101 開始，首次執行會自動建立預設雲端環境，因此在嘗試之前無需進行網頁設定步驟。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/aFXPQxiBOW99MHS3/images/whats-new/ultraplan.mp4?fit=max&auto=format&n=aFXPQxiBOW99MHS3&q=85&s=e8f2f23730c6a5c289dbf3e7b13eadf6" />

執行命令，或在任何提示中包含關鍵字：

```text title="Claude Code" wrap theme={null}
/ultraplan migrate the auth service from sessions to JWTs
```

[Ultraplan 指南](https://code.claude.com/docs/zh-TW/ultraplan)

Monitor 工具
v2.1.98

一個新的內建工具，可生成背景監視程式並將其事件串流到對話中：每個事件都會作為新的文字記錄訊息出現，Claude 會立即對其做出反應。追蹤訓練執行、監督 PR 的 CI，或在開發伺服器當機時立即自動修復，所有這些都無需 Bash sleep 迴圈佔用回合。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/aFXPQxiBOW99MHS3/images/whats-new/monitor-tool.mp4?fit=max&auto=format&n=aFXPQxiBOW99MHS3&q=85&s=f4156c15a0999de5c5157f54a3117c89" />

要求 Claude 在您繼續工作時監視某些內容：

```text title="Claude Code" wrap theme={null}
Tail server.log in the background and tell me the moment a 5xx shows up
```

這與 `/loop` 配對，現在可自我調整：省略間隔，Claude 會根據任務排定下一個時刻，或使用 Monitor 工具來完全跳過輪詢。

```text title="Claude Code" wrap theme={null}
/loop check CI on my PR
```

[Monitor 工具參考](https://code.claude.com/docs/zh-TW/tools-reference.md#monitor-tool)

/autofix-pr
CLI

PR 自動修復在第 13 週登陸網頁版。現在您可以在不離開終端的情況下啟用它：`/autofix-pr` 推斷您目前分支的開放 PR，並在一個步驟中為網頁上的 Claude Code 啟用自動修復。推送您的分支、執行命令、離開；Claude 監視 CI 和審查評論，並推送修復直到通過。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/aFXPQxiBOW99MHS3/images/whats-new/autofix-pr.mp4?fit=max&auto=format&n=aFXPQxiBOW99MHS3&q=85&s=95f191eb4711130a128aec3f6b720527" />

從 PR 的分支執行：

```text title="Claude Code" wrap theme={null}
/autofix-pr
```

[自動修復拉取請求](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#auto-fix-pull-requests)

/team-onboarding
v2.1.101

從您的本機 Claude Code 使用情況產生團隊入職指南。在您熟悉的專案中執行它，並將輸出交給新團隊成員，以便他們可以重新執行您的設定，而不是從預設值開始。

在您花費真實時間的專案中執行：

```text title="Claude Code" wrap theme={null}
/team-onboarding
```

[命令參考](https://code.claude.com/docs/zh-TW/commands.md)

其他成就

焦點檢視：在無閃爍模式中按 `Ctrl+O` 以將檢視摺疊到您的最後提示、單行工具摘要（含 diffstats）和 Claude 的最終回應登入畫面上的引導式 [Amazon Bedrock](https://code.claude.com/docs/zh-TW/amazon-bedrock.md) 和 [Google Cloud 的 Agent Platform](https://code.claude.com/docs/zh-TW/google-vertex-ai.md) 設定精靈：選擇「第三方平台」以進行逐步驗證、區域、認證檢查和模型固定`/agents` 獲得標籤式版面配置：「執行中」標籤顯示帶有 `● N running` 計數的即時子代理，加上「執行代理」和「檢視執行中的執行個體」動作在「程式庫」標籤中預設工作量級別現在對 API 金鑰、Amazon Bedrock、Google Cloud 的 Agent Platform、Microsoft Foundry、Team 和 Enterprise 使用者為 `high`（使用 `/effort` 控制）`/cost` 為訂閱使用者顯示每個模型和快取命中的細目分類`/release-notes` 現在是互動式版本選擇器狀態列：新的 `refreshInterval` 設定每 N 秒重新執行命令，JSON 輸入中的 `workspace.git_worktree``CLAUDE_CODE_PERFORCE_MODE`：Edit/Write 在唯讀檔案上失敗，並提示 `p4 edit`，而不是無聲地覆寫OS CA 憑證存放區現在預設受信任，因此企業 TLS 代理無需額外設定即可運作（`CLAUDE_CODE_CERT_STORE=bundled` 以選擇退出）由 Mantle 提供支援的 Amazon Bedrock：設定 `CLAUDE_CODE_USE_MANTLE=1`強化的 Bash 工具權限：反斜線轉義旗標、環境變數前綴、`/dev/tcp` 重新導向和複合命令現在會正確提示`UserPromptSubmit` hooks 可以透過 `hookSpecificOutput.sessionTitle` 設定工作階段標題

[v2.1.92–v2.1.101 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-92)

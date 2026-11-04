<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w25 | lastmod: 2026-09-10 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w25（官方 zh-TW，lastmod 2026-09-10）｜分類：What's New › What's New｜EN 摘要：Publish a live, shareable page from your session with Artifacts, match tool parameters in deny and ask rules, and set any setting from the prompt with /config.

# 第 25 週 · 2026 年 6 月 15–19 日

> 從您的工作階段使用 Artifacts 發佈即時可分享的頁面、在拒絕和詢問規則中比對工具參數，以及使用 /config 從提示設定任何設定。

版本 [v2.1.178 → v2.1.183](https://code.claude.com/docs/en/changelog.md#2-1-178)
3 項功能 · 6 月 15–19 日

Artifacts

Artifact 是一個即時互動式頁面，Claude Code 從您的工作階段發佈到 claude.ai 上的私人 URL，並在工作階段繼續進行時在原地更新。當終端文字不是合適的媒介時，請要求一個，例如帶有內聯註解差異的 PR 逐步解說或從工作階段資料建立的儀表板。Artifacts 在 Team 和 Enterprise 方案上處於測試版。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/1ylKDoQynT1UgfEK/images/whats-new/artifacts.mp4?fit=max&auto=format&n=1ylKDoQynT1UgfEK&q=85&s=7f5391559d2bc69989621b36322fcff1" />

向 Claude 要求一個頁面，然後批准發佈提示：

```text title="Claude Code" wrap theme={null}
Make an artifact that walks through this PR with the diff annotated inline.
```

[建立 artifact](https://code.claude.com/docs/zh-TW/artifacts.md#create-an-artifact)

按輸入參數比對
v2.1.178

拒絕和詢問權限規則現在可以使用 `Tool(param:value)` 語法比對工具的輸入參數。例如，`Agent(model:opus)` 比對要求 Opus 模型層級的子代理生成。該值接受 `*` 作為萬用字元，因此 `Agent(isolation:*)` 比對任何明確的隔離值。

在 `settings.json` 中將參數規則新增到拒絕清單：

```json .claude/settings.json {3} theme={null}
{
  "permissions": {
    "deny": ["Agent(model:opus)"]
  }
}
```

[按輸入參數比對](https://code.claude.com/docs/zh-TW/permissions.md#match-by-input-parameter)

從提示設定任何設定
v2.1.181

將 `key=value` 傳遞給 `/config` 以直接變更設定，無需開啟設定介面。該語法也適用於使用 `-p` 旗標的非互動模式和遠端控制。

從提示設定 `thinking` 設定：

```text title="Claude Code" wrap theme={null}
/config thinking=false
```

[命令參考](https://code.claude.com/docs/zh-TW/commands.md#all-commands)

其他成果

自動模式現在在您未要求捨棄本機工作時會阻止破壞性 git 命令（`git reset --hard`、`git clean -fd`、`git stash drop`），並在您未要求特定堆疊時阻止 `terraform destroy`將新的 `attribution.sessionUrl` 設定設為 `false` 以在網頁和遠端控制工作階段中的提交和 PR 中省略 claude.ai 工作階段連結在 `/config` 介面中，Enter 和 Space 都會變更選定的設定，Esc 現在會儲存並關閉而不是還原新的 `sandbox.allowAppleEvents` 選擇加入設定讓沙箱命令在 macOS 上傳送 Apple Events將 `CLAUDE_CLIENT_PRESENCE_FILE` 指向標記檔案以在您在機器上時抑制行動推播通知長段落現在逐行串流而不是等待第一個換行符API 連線在思考中斷開現在會自動重試，而不是顯示「思考時連線已關閉」設定 `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 時，每個工作階段都有一個隱含的團隊，因此您可以直接使用 Agent 工具的 `name` 參數生成隊友嵌套 `.claude/skills` 目錄中的技能在處理該處的檔案時會載入；在名稱衝突時，嵌套技能顯示為 `<dir>:<name>`，因此兩者都保持可用修正了提示快取在自訂 `ANTHROPIC_BASE_URL` 和 Foundry 上未讀取的問題修正了 Write 和 Edit 在網路磁碟機和雲端同步資料夾上產生零位元組或截斷檔案的問題

[v2.1.178–v2.1.183 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-178)

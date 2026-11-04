<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w14 | lastmod: 2026-09-25 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w14（官方 zh-TW，lastmod 2026-09-25）｜分類：What's New › What's New｜EN 摘要：Computer use in the CLI, interactive in-product lessons, flicker-free rendering, per-tool MCP result-size overrides, and plugin executables on PATH.

# 第 14 週 · 3 月 30 日 – 4 月 3 日，2026 年

> CLI 中的電腦使用、互動式產品內課程、無閃爍渲染、按工具 MCP 結果大小覆蓋，以及 PATH 上的外掛程式可執行檔。

版本 [v2.1.86 → v2.1.91](https://code.claude.com/docs/en/changelog.md#2-1-86)
5 項功能 · 3 月 30 日 – 4 月 3 日

CLI 中的電腦使用
研究預覽

上週電腦使用功能登陸了桌面應用程式。本週它進入了 CLI：Claude 可以打開原生應用程式、點擊 UI、測試自己的更改，以及修復損壞的內容，全部都在您的終端中進行。Web 應用程式已經有驗證迴圈；原生 iOS、macOS 和其他僅限 GUI 的應用程式沒有。現在有了。最適合用於關閉沒有 API 可調用的應用程式和工具的迴圈。仍處於早期階段；預期會有粗糙的邊緣。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/CfffsX01JHFnIKvD/images/whats-new/cli-computer-use.mp4?fit=max&auto=format&n=CfffsX01JHFnIKvD&q=85&s=c17a337902308d7c9121013ded0494db" />

需要 macOS 和 Pro 或 Max 方案；否則，`computer-use` 不會出現在 `/mcp` 中。運行 `/mcp`，找到 `computer-use`，然後將其打開。然後要求 Claude 端到端驗證更改：

```text title="Claude Code" wrap theme={null}
Open the iOS simulator, tap through onboarding, and screenshot each step
```

[電腦使用指南](https://code.claude.com/docs/zh-TW/computer-use.md)

/powerup
v2.1.90

互動式課程，通過動畫演示教授 Claude Code 功能，直接在您的終端內進行。Claude Code 發佈頻繁，上個月會改變您工作方式的功能可能會被忽視。運行一次 `/powerup`，您就會知道有什麼功能。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/CfffsX01JHFnIKvD/images/whats-new/powerup.mp4?fit=max&auto=format&n=CfffsX01JHFnIKvD&q=85&s=fb88beddc0ecc8029da5ab029e4b28f1" />

運行它：

```text title="Claude Code" wrap theme={null}
/powerup
```

[命令參考](https://code.claude.com/docs/zh-TW/commands.md)

無閃爍渲染
v2.1.89

選擇加入具有虛擬化回滾的新替代屏幕渲染器。提示輸入保持固定在底部，滑鼠選擇可跨長對話進行，重繪時的閃爍消失了。取消設置 `CLAUDE_CODE_NO_FLICKER` 以回滾。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/CfffsX01JHFnIKvD/images/whats-new/flicker-free.mp4?fit=max&auto=format&n=CfffsX01JHFnIKvD&q=85&s=7719e35e52a3f9734b0cf69edac333ad" />

設置環境變數並重新啟動 Claude Code：

```bash theme={null}
export CLAUDE_CODE_NO_FLICKER=1
claude
```

[全屏渲染](https://code.claude.com/docs/zh-TW/fullscreen.md)

MCP 結果大小覆蓋
v2.1.91

MCP 伺服器作者現在可以通過在工具的 `tools/list` 條目中設置 `anthropic/maxResultSizeChars` 來提高特定工具的截斷上限，最高可達 500K 字符的硬上限。上限曾經是全局的，因此偶爾返回固有大型有效負載（如資料庫架構或完整文件樹）的工具會達到預設限制，並使用文件參考持久化到磁碟。按工具覆蓋在工具真正需要時將這些結果保持內聯。

在您的伺服器的 `tools/list` 響應中註釋工具：

```json highlight={5} theme={null}
{
  "name": "get_schema",
  "description": "Returns the full database schema",
  "_meta": {
    "anthropic/maxResultSizeChars": 500000
  }
}
```

[MCP 參考](https://code.claude.com/docs/zh-TW/mcp.md#raise-the-limit-for-a-specific-tool)

PATH 上的外掛程式可執行檔
v2.1.91

在外掛程式根目錄的 `bin/` 目錄中放置可執行檔，Claude Code 會在外掛程式啟用時將該目錄添加到 Bash 工具的 `PATH`。Claude 然後可以從任何 Bash 工具調用中將二進制檔案作為裸命令調用，無需絕對路徑或包裝器指令碼。便於將 CLI 幫助程式與調用它們的命令、代理和鉤子一起打包。

在外掛程式根目錄添加 `bin/` 目錄：

```text highlight={4, 5} theme={null}
my-plugin/
├── .claude-plugin/
│   └── plugin.json
└── bin/
    └── my-tool
```

[外掛程式參考](https://code.claude.com/docs/zh-TW/plugins/manifest-reference.md#standard-layout)

其他成就

自動模式後續：新的 `PermissionDenied` 鉤子在分類器拒絕時觸發（返回 `retry: true` 讓 Claude 嘗試不同的方法），`/permissions` → 最近拒絕讓您使用 `r` 手動重試`PreToolUse` 鉤子中 `permissionDecision` 的新 `defer` 值：`-p` 會話在工具調用處暫停並以 `deferred_tool_use` 有效負載退出，以便 SDK 應用程式或自訂 UI 可以呈現它，然後使用 `--resume` 恢復`/buddy`：孵化一個小生物來觀看您編碼。一個愚人節玩笑，不再可用`disableSkillShellExecution` 設定阻止來自技能、斜杠命令和外掛程式命令的內聯 shell編輯工具現在可以在通過 `cat` 或 `sed -n` 查看的文件上工作，無需單獨的 Read超過 50K 的鉤子輸出保存到磁碟，帶有路徑 + 預覽，而不是注入到上下文中思考摘要在互動式會話中預設關閉（`showThinkingSummaries: true` 以恢復）語音模式：推送通話修飾符組合、Windows WebSocket、macOS Apple Silicon 麥克風權限`claude-cli://` 深層連結接受多行提示（編碼 `%0A`）

[v2.1.86–v2.1.91 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-86)

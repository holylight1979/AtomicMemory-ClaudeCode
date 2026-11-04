<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w13 | lastmod: 2026-09-10 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w13（官方 zh-TW，lastmod 2026-09-10）｜分類：What's New › What's New｜EN 摘要：Auto mode for hands-off permissions, computer use built in, PR auto-fix in the cloud, transcript search, and a PowerShell tool for Windows.

# 第 13 週 · 2026 年 3 月 23–27 日

> 自動模式用於免提權限、內建電腦使用、雲端 PR 自動修復、文字稿搜尋，以及適用於 Windows 的 PowerShell 工具。

發佈版本 [v2.1.83 → v2.1.85](https://code.claude.com/docs/en/changelog.md#2-1-83)
6 項功能 · 3 月 23–27 日

自動模式
研究預覽

自動模式將您的權限提示交給分類器。安全的編輯和命令無需中斷您即可執行；任何破壞性或可疑的操作都會被阻止並顯示。這是批准每個檔案寫入和使用 `--dangerously-skip-permissions` 執行之間的折衷方案。

![Claude Code 提示頁尾顯示黃色的'自動模式開啟 (Shift+Tab 切換)'指示器](https://mintcdn.com/claude-code/CfffsX01JHFnIKvD/images/whats-new/auto-mode.png?fit=max\&auto=format\&n=CfffsX01JHFnIKvD\&q=85\&s=367c9e9d4ba5bc57ec4b935154bf1fbb)

使用 Shift+Tab 切換到自動模式，或將其設定為預設值：

```json ~/.claude/settings.json {3} theme={null}
{
  "permissions": {
    "defaultMode": "auto"
  }
}
```

[權限模式指南](https://code.claude.com/docs/zh-TW/permission-modes.md)

電腦使用
Desktop

Claude 現在可以從 Claude Code Desktop 應用程式控制您的實際桌面：開啟原生應用程式、點擊 iOS 模擬器、驅動硬體控制面板，以及驗證螢幕上的變更。預設為關閉，並在每個操作前詢問。最適合用於其他方法無法達到的事項：沒有 API 的應用程式、專有工具、任何只以 GUI 形式存在的東西。

![Claude Desktop 設定，已啟用'電腦使用'切換，顯示允許 Claude 在您允許的應用程式中進行螢幕截圖並控制鍵盤和滑鼠的選項](https://mintcdn.com/claude-code/CfffsX01JHFnIKvD/images/whats-new/computer-use.png?fit=max\&auto=format\&n=CfffsX01JHFnIKvD\&q=85\&s=d631de2017edafff463505f8ddbc0f51)

在設定中啟用它，授予作業系統權限，然後要求 Claude 端對端驗證變更：

```text title="Claude Code" wrap theme={null}
Open the iOS simulator, tap through the onboarding flow, and screenshot each step
```

[電腦使用指南](https://code.claude.com/docs/zh-TW/desktop.md#let-claude-use-your-computer)

PR 自動修復
Web

開啟 PR 時翻轉開關並離開。Claude 監視 CI、修復失敗、處理細節，並推送直到變綠。不再需要透過六輪 lint 錯誤來監督 PR。

![Claude Code 網頁 CI 面板顯示已啟用'自動修復'切換，描述為'主動修復 CI 失敗和審查評論'](https://mintcdn.com/claude-code/CfffsX01JHFnIKvD/images/whats-new/auto-fix.png?fit=max\&auto=format\&n=CfffsX01JHFnIKvD\&q=85\&s=c62b181c6c5d96929f0b43525f9f3584)

在 Claude Code 網頁上建立 PR 後，在 CI 面板中切換「自動修復」。

[自動修復提取請求](https://code.claude.com/docs/zh-TW/claude-code-on-the-web.md#auto-fix-pull-requests)

文字稿搜尋
v2.1.83

在文字稿模式中按 `/` 搜尋您的對話。`n` 和 `N` 逐步瀏覽符合項目。最後有辦法找到 Claude 在 400 條訊息前執行的那個 Bash 命令。

開啟文字稿模式並搜尋：

```text Claude Code theme={null}
Ctrl+O    # open transcript
/migrate  # search for "migrate"
n         # next match
N         # previous match
```

[全螢幕指南](https://code.claude.com/docs/zh-TW/fullscreen.md#search-and-review-the-conversation)

PowerShell 工具
preview
v2.1.84

Windows 獲得了與 Bash 並行的原生 PowerShell 工具。Claude 可以執行 cmdlet、管道物件，以及使用 Windows 原生路徑，無需透過 Git Bash 翻譯所有內容。

從設定中選擇加入：

```json .claude/settings.json {3} theme={null}
{
  "env": {
    "CLAUDE_CODE_USE_POWERSHELL_TOOL": "1"
  }
}
```

[PowerShell 工具文件](https://code.claude.com/docs/zh-TW/tools-reference.md#powershell-tool)

條件式 hooks
v2.1.85

Hooks 現在可以使用權限規則語法宣告 `if` 欄位。您的 pre-commit 檢查只會針對 `Bash(git commit *)` 生成，而不是每個 bash 呼叫，減少繁忙工作階段中的程序開銷。

將 hook 限制為僅 git 提交：

```json .claude/settings.json {5} theme={null}
{
  "hooks": {
    "PreToolUse": [{
      "hooks": [{
        "if": "Bash(git commit *)",
        "type": "command",
        "command": ".claude/hooks/lint-staged.sh"
      }]
    }]
  }
}
```

[Hooks 參考](https://code.claude.com/docs/zh-TW/hooks.md)

其他成果

Plugin `userConfig` 現已公開：在啟用時提示設定、鑰匙圈支援的祕密貼上的影像插入 `[Image #N]` 晶片，您可以按位置參考`managed-settings.d/` 分層原則片段的放置目錄`CwdChanged` 和 `FileChanged` hook 事件用於 direnv 風格的設定代理程式可以在 frontmatter 中宣告 `initialPrompt` 以自動提交第一個回合`Ctrl+X Ctrl+E` 開啟您的外部編輯器，符合 readline在任何回應前中斷會自動恢復您的輸入`/status` 現在在 Claude 回應時也能運作深層連結在您偏好的終端中開啟，而不是首次偵測到的閒置返回提示在離開 75 分鐘以上後執行 `/clear`VS Code：速率限制橫幅、Esc 兩次倒帶選擇器

[v2.1.83–v2.1.85 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-83)

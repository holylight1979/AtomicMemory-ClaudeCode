<!-- harvested: 2026-11-04 | source: https://code.claude.com/docs/zh-TW/whats-new/2026-w28 | lastmod: 2026-09-09 | section: What's New / What's New -->
> 來源：https://code.claude.com/docs/zh-TW/whats-new/2026-w28（官方 zh-TW，lastmod 2026-09-09）｜分類：What's New › What's New｜EN 摘要：Browse external sites from the Desktop app's built-in browser, run a full setup checkup with /doctor, and pick up auto mode transcript protections and agent view upgrades.

# 第 28 週 · 2026 年 7 月 6–10 日

> 從桌面應用程式的內建瀏覽器瀏覽外部網站、使用 /doctor 執行完整設定檢查，以及取得自動模式文字記錄保護和代理程式檢視升級。

版本 [v2.1.202 → v2.1.206](https://code.claude.com/docs/en/changelog.md#2-1-202)
2 項功能 · 7 月 6–10 日

桌面上的應用程式內瀏覽器
Desktop

桌面上的 Claude Code 現在具有內建瀏覽器。Claude 可以調出文件、設計或任何其他網站，並以與本機開發伺服器預覽相同的方式讀取、點擊和與頁面互動。瀏覽器是沙箱化的且可配置的：您可以選擇瀏覽工作階段是否持續，安全分類器會審查外部網站上的操作。

<video autoPlay muted loop playsInline src="https://mintcdn.com/claude-code/x358isu_VzLnyTEN/images/whats-new/desktop-browser.mp4?fit=max&auto=format&n=x358isu_VzLnyTEN&q=85&s=8033e85a1cb0a37870a79e702c18f4e4" />

[瀏覽外部網站](https://code.claude.com/docs/zh-TW/desktop.md#browse-external-sites)

/doctor 是完整設定檢查
v2.1.205

`/doctor` 現在可以診斷問題並修復它們，而不是列印唯讀報告。它檢查安裝健康狀況、尋找未使用的技能、MCP 伺服器和外掛程式與其背景成本、對本機 `CLAUDE.md` 檔案與簽入的檔案進行重複資料刪除、建議修剪 Claude 可以從程式碼庫衍生的 `CLAUDE.md` 內容，以及標記緩慢的 hooks。它首先報告發現，並在變更任何內容之前要求確認。`/checkup` 是其別名。

從任何工作階段執行檢查：

```text Claude Code theme={null}
> /doctor
```

[所有命令](https://code.claude.com/docs/zh-TW/commands.md#all-commands)

其他成果

自動模式現在會阻止篡改工作階段文字記錄檔案，並在執行 `rm -rf` 於無法從背景解析的變數時詢問`/cd` 現在在您輸入時建議目錄路徑，符合 `/add-dir``/commit-push-pr` 自動允許 `git push` 到儲存庫的已配置推送遠端，除了 `origin`閘道：`/login` 現在支援 Anthropic 營運的公開閘道端點`EnterWorktree` 在進入專案 `.claude/worktrees/` 目錄外的 git worktree 之前要求確認背景代理程式在 Claude Code 更新後立即在背景升級到新版本，而不是在您附加時支付緩慢的過時工作階段升級代理程式檢視列現在顯示彩色狀態字和分類器撰寫的標題，而不是原始工具呼叫文字，編輯、合併、評論或推送到現有 PR 的工作階段會在 `claude agents` 中連結它自動更新二進位檔案下載現在串流到磁碟，而不是在記憶體中緩衝，將更新程式的尖峰記憶體使用量減少約 400 MB背景工作通知現在明確說明沒有發生人工輸入，防止虛構的文字記錄內核准被執行改進了 Opus 4.8 上所有工作量級別的 `/code-review` 發現品質

[v2.1.202–v2.1.206 的完整變更日誌 →](https://code.claude.com/docs/en/changelog.md#2-1-202)

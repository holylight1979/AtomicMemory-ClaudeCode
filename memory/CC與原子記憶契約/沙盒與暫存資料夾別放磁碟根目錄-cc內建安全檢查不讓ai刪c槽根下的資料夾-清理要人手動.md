# 沙盒與暫存資料夾別放磁碟根目錄-cc內建安全檢查不讓ai刪c槽根下的資料夾-清理要人手動

- Scope: global
- Author: holylight
- Source: session bc7c5340 開發期暫存清理
- Confidence: [臨]
- Trigger: 磁碟根目錄, rm -rf 被擋, Dangerous rm operation, 量測沙盒, 受測專案放哪, 暫存資料夾清理, C:\\w1, critical system directory
- Created-at: 2026-10-29
- Quote: 「對了，提醒：完成以後請記得要檢查一次所有 INDEX檔案是否都有正確更新。」

## 知識

- [臨] Claude Code 內建安全檢查把磁碟根目錄下的資料夾（例 `/c/w1`、`C:\w1`）當「critical system directory」：`rm -rf` 一律拒絕，訊息「Dangerous rm operation detected」，不是使用者拒絕、權限規則也放不行，且明令不准拆指令或換工具繞過。只能請使用者自己刪。
- [臨] 同一條指令裡夾著一個被擋的目標，整條都不執行；要把可刪的目標（家目錄下的子夾、repo 內的夾）拆成另一條先刪。
- [臨] 所以量測沙盒、受測假專案、無頭實跑資料根要建在家目錄或系統暫存下的子夾（例 `%TEMP%\<用途>\` 或 `~/.claude-wt/<用途>/`），AI 收尾時才清得掉。

## 行動

- 建量測沙盒或受測專案前，路徑選家目錄或暫存下的子夾，不放 C:\ 根
- 遇到 Dangerous rm operation：可刪的目標拆出來先刪，被擋的整理成一行 Remove-Item 給使用者

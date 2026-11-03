# 腳本跳windows通知走powershell-winrt-toastnotificationmanager-appid用powershell自己的-文字走環境變數不拼字串-discord用webhook-post-content上限2000

- Scope: global
- Author: holylight
- Source: GitLab ClaudeCode-AtomMemory !14 tools/usage-watch.py TOAST_PS／toast／discord_post／notify（作者 prog_katana_batch，合併 d09f9640）
- Confidence: [臨]
- Trigger: Windows 通知, toast, ToastNotification, 桌面通知, Discord, webhook, 通知管道, 跳通知, WinRT, AppId, notify
- Created-at: 2026-11-03
- Quote: 「收割，我希望是從他們推的MR中，汲取此電腦所用LLM所欠缺的知識、經驗」

## 知識

- [臨] 純腳本（沒有安裝的 App）要跳 Windows 桌面通知：PowerShell 載 `[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]`，`GetTemplateContent(ToastText02)` 填兩個 text 節點，`CreateToastNotifier($app).Show(...)`；`$app` 用 PowerShell 自己的 AppUserModelId `{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe`，不必註冊新 AppId。
- [臨] 標題與內文用環境變數（`$env:UW_TITLE`、`$env:UW_BODY`）傳進 PowerShell，不要拼進 -Command 字串：中文、引號、換行都不用跳脫；Python 端 `subprocess.run(..., env={**os.environ, ...}, creationflags=CREATE_NO_WINDOW)`。
- [臨] Discord 通知：對 webhook 網址 POST JSON `{"content": text}`，content 上限 2000 字要先截；網址等同發文權限，放本機不進版控的 settings.json，錯誤訊息裡也不要帶網址。
- [臨] 多管道通知的回傳形狀：(至少一個管道送達, {管道: 錯誤})；沒設定 webhook 不算錯，只有設定了卻發不出去才算。

## 行動

- 腳本要桌面通知：套上面 PowerShell WinRT 片段，AppId 用 PowerShell 的
- 通知文字一律走環境變數進 PowerShell
- webhook 網址只放本機 settings 檔；錯誤訊息剔掉網址

# 自動化開claude-ai用量頁-headless-Edge撞Cloudflare人類驗證-日常Chrome-profile被鎖不可借用-改專屬Chrome-profile一次登入

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: claude.ai, 用量截圖, usage snapshot, Cloudflare, headless, launch_persistent_context, channel chrome, Chrome profile, Cookies WinError 32, Register-ScheduledTask, WakeToRun, SC_MONITORPOWER, LockWorkStation, SeShutdownPrivilege, SetSuspendState, powercfg /requests
- Created-at: 2026-09-21
- Related: 在使用者活躍桌面彈視窗做gui實驗會被順手關掉污染數據-改headless-edge加cdp或先查前景視窗

## 知識

- [臨] Cloudflare：claude.ai 對 headless（Edge 或 Chrome、含已登入 profile、加 AutomationControlled/--enable-automation 遷移）一律卡「驗證您是人類」（title=請稍候...）；同 profile 改有頭立刻放行。排程截圖就讓它彈視窗。
- [臨] 登入狀態：日常 Chrome 的 Cookies 檔開著時 copy 直接 WinError 32，且新版 Chrome 拒絕在預設 profile 上自動化——不借用；工具專屬 `user_data_dir` + `channel="chrome"`，`--login` 有頭登入一次即可（使用者登入在 Chrome，不選 Edge）。
- [臨] 螢幕狀態：關螢幕（SC_MONITORPOWER）、鎖定（LockWorkStation）下 Playwright 截圖都正常（亮度 214）——走 Chromium 合成器非抓螢幕；抓螢幕類工具才會黑圖。只有登出、關機不行（排程為 Interactive logon）。
- [臨] 睡眠：CC 工具程序與 Task Scheduler 啟動的程序 token 都無 SeShutdownPrivilege，`SetSuspendState` 回 True 但不睡（force 時 1314）；使用者機器電源計畫睡眠=永不、且 NVIDIA HD Audio「音訊串流使用中」持續擋閒置睡眠（07-31 起無 Kernel-Power 42/107）。「螢幕黑掉」= 關螢幕非睡眠。
- [臨] 排程用 `Register-ScheduledTask` 才能給 -WakeToRun -StartWhenAvailable；pythonw 靜默跑。在使用者活躍桌面彈有頭視窗測試會被順手關（TargetClosedError），先講再彈。

## 行動

- 要自動化 claude.ai 頁面：channel=chrome + 專屬 profile + 有頭；先跑 --login 一次
- headless 撞「請稍候...」title → 是 Cloudflare 擋 headless，直接改有頭
- 要驗螢幕關/鎖定下的截圖，用 SC_MONITORPOWER / LockWorkStation 模擬後量圖片亮度
- 需要讓機器睡眠的測試得提權，別在非提權程序裡試

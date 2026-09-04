# Unity-Editor崩潰鑑識三路徑-事件檔1000先看故障模組-EDR注入DLL可能是真兇

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: Unity crash, Unity 崩潰, Editor 閃退, Native Crash Reporting, Got a UNKNOWN, InProcessClient64.dll, SentinelOne, EDR, Application Error 1000, CrashDumps, Editor-prev.log, c0000005, WER
- Created-at: 2026-09-02
- Related: (none)

## 知識

- [臨] Unity Editor 崩潰時 Editor.log 尾端只有「Native Crash Reporting / Got a UNKNOWN while executing native code」且 Managed Stacktrace 為空 → 這段本身不含原因，別在 log 尾端的最後幾筆錯誤上腦補因果；崩點要靠 OS 層資料
- [臨] 鑑識三路徑（依成本排）：① Windows 事件檔 Application 來源「Application Error」Id 1000 → 直接給「失敗的模組名稱 + 例外代碼 + 位移」；② %LOCALAPPDATA%\CrashDumps\Unity.exe.<pid>.dmp（本機開了 LocalDumps 時）；③ %LOCALAPPDATA%\Temp\Unity\Editor\Crashes\ 只在 Unity 自己的 crash handler 有接到時才產生，接不到（例如被注入 DLL 炸掉）就沒新資料夾
- [臨] 實測案例：故障模組是 SentinelOne 端點防護的 InProcessClient64.dll（注入 Unity.exe 的 EDR hook）、c0000005 存取違規 → 是 EDR 自己的 bug，不是專案碼；同機 6 月的舊崩潰故障模組是 Unity.exe 本體，兩者不同因，比對歷史用 C:\ProgramData\Microsoft\Windows\WER\ReportArchive\AppCrash_Unity.exe_*\Report.wer（UTF-16，要 iconv 後 grep Sig[3]/Sig[6].Value）
- [臨] Unity 重啟會把崩掉實例的 log 輪替成 Editor-prev.log，鑑識前先 cp 到 scratchpad 存證（大檔 50MB 級，用 grep -n 定位、sed -n 切段，不整檔 cat）

## 行動

- Unity 崩潰先跑 Get-WinEvent Application Error Id 1000 看故障模組，再決定要不要追專案碼
- 故障模組是防毒／EDR DLL → 回報 IT 把 Unity.exe 與專案目錄加排除，專案碼不改
- 崩掉當下先 cp Editor-prev.log 存證再分析

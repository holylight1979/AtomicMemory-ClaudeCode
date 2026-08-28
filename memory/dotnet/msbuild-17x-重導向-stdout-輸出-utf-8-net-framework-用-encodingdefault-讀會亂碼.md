# MSBuild 17.x 重導向 stdout 輸出 UTF-8-net-framework-用-Encoding.Default-讀會亂碼

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: MSBuild, 亂碼, StandardOutputEncoding, Encoding.Default, Big5, cp950, RedirectStandardOutput, 編譯 log, ProcessStartInfo, UTF-8
- Created-at: 2026-08-28
- Related: gpt-sgiserlauncher-工具-危險點與架構約束, svn-commit-中文訊息在-cp950-主控台會亂碼-必加-encoding-utf-8

## 知識

- [臨] MSBuild 17.14（VS2022）在 stdout/stderr 被重導向時輸出 **UTF-8** 位元組（實測 hexdump：`e7 9a 84`=「的」，iconv 驗證整檔合法 UTF-8），與主控台字碼頁 950 無關。
- [臨] .NET Framework 下 `Encoding.Default` = 系統 ANSI（台灣 = Big5/950）；.NET Core+ 下 `Encoding.Default` = UTF-8。同一行碼在兩個 runtime 意義不同。
- [臨] 用 `ProcessStartInfo.StandardOutputEncoding = Encoding.Default` 讀 MSBuild 輸出 → UTF-8 位元組被當 Big5 拆讀，中文警告訊息變成 `擅寫??` 類亂碼（無效序列被換成 `?`）。實例：GPT_SGISerLauncher「編譯全部」路徑。
- [臨] 只設 StandardOutputEncoding 不設 StandardErrorEncoding，stderr 仍走 Default，錯誤行照樣亂碼。

## 行動

- ProcessStartInfo 呼叫 MSBuild / dotnet CLI 並重導向輸出 → StandardOutputEncoding 與 StandardErrorEncoding 都設 Encoding.UTF8
- 看到子行程輸出亂碼先 hexdump 原始位元組 + iconv 驗證，確定來源編碼再改解碼端，別猜
- 呼叫舊版 .NET Framework 伺服器 exe（依主控台字碼頁輸出）的路徑維持 Default，勿一刀切全改 UTF8

# 輸出exe被執行中行程鎖住-建置驗證改輸出目錄-行為驗證add-type載dll跑自測

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: MSB3026, MSB3027, 檔案鎖定, being used by another process, dotnet build, OutputPath, Add-Type, 自測, 驗證證據, app 執行中
- Created-at: 2026-08-21
- Related: 併發session共用的不只工作樹-執行中的應用程式行程也是共用資源, 離線測試過但實機不過-先排除實機跑的不是這份程式碼, powershell傳null給dotnet-string參數會變空字串-nullstring才是真null

## 知識

- [臨] **使用者的 app 正在執行時，`dotnet build` 會在最後複製 exe 那步吃 MSB3026 重試→MSB3027 失敗（exit 1）**，但 CS 編譯其實已完成——別誤判成程式碼壞掉，也別殺使用者的行程（執行中的應用程式是併發共用資源）。要拿乾淨的建置證據：`dotnet build -p:OutputPath=<scratchpad>\buildout\`——輸出改道就不撞鎖，ExitCode=0 可核對。
- [臨] **WinForms 專案的純邏輯自測可以不開 UI 直接驗**：把剛編出的 dll 用 PowerShell `Add-Type -Path <dll>` 載入，直接呼叫 `[Namespace.SelfTest]::Run()` 這類靜態方法拿實跑結果（實測 net8.0-windows 組件在 pwsh 可載可跑）。比「編譯過≒行為對」強一個等級的證據，收尾宣稱前值得花這一步。
- [臨] 前提：自測方法零 UI 相依（只回 List<string> 之類）——這也是把回歸自測寫成純靜態方法、與 UI 分離的另一個紅利。
- [臨] **報告措辭（使用者明確要求）**：改輸出目錄建置＋跑自測只證明新碼邏輯，**不會**讓使用者開著的程式變新版。只要 build 有 MSB3021，收尾第一句就寫「程式碼編譯通過，但 exe 沒更新成功（程式開著擋住複製），你在跑的還是舊版」，不得只說「編譯通過」帶過；宣告可以測前先驗 bin exe LastWriteTime 與進程 StartTime。

## 行動

- build 因檔案鎖 exit 1 時：先分辨 CS 錯誤與 MSB 複製錯，改 OutputPath 重跑取證，不殺行程
- 宣稱行為正確前，優先用 Add-Type 載 dll 實跑自測而非只給編譯證據

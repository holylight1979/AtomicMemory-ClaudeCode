# powershell傳null給dotnet-string參數會變空字串-NullString才是真null

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: PowerShell, $null, NullString, 反射呼叫, LoadFrom, optional 參數, 空字串, 診斷誤報
- Created-at: 2026-08-21
- Related: 輸出exe被執行中行程鎖住-建置驗證改輸出目錄-行為驗證add-type載dll跑自測, 否證假說前先確認樣本涵蓋待測狀態的變化-受控實驗勝過觀察性交叉比對

## 知識

- [臨] PowerShell 把 `$null` 傳給 .NET 方法的 string 參數時會自動轉成**空字串 ""**，不是真 null——`Method($null)` 走的是 `Method("")`。要傳真 null 必須用 `[NullString]::Value`。
- [臨] 危險場景：C# 方法用 `string? x = null` 當「不過濾/全部」語意（如 `Diagnose(zone: null)` = 全圖），PowerShell 端 `$null` 變 "" 後改走「過濾等於空字串」→ 篩不到任何東西**靜默回空集合**——診斷腳本會誤報「0 問題」，比丟例外更毒。實例：MudClient 地圖全圖診斷，$null 得 0 筆、[NullString]::Value 得 5 筆。
- [臨] 用 PowerShell + LoadFrom 載 DLL 跑 .NET 自測/診斷時，凡 optional string 參數一律顯式傳 `[NullString]::Value` 或改用無參 overload；拿到「0 筆」結果先懷疑參數綁定，用已知有問題的樣本反證（本例：手動核對一條已知壞邊）。

## 行動

- （依知識內容判斷）

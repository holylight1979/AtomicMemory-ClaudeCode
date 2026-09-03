# WinForms 多選資料夾 — .NET 8 無 Multiselect 須走 IFileOpenDialog

- Scope: global
- Audience: programmer
- Author: holylight
- Confidence: [固]
- Trigger: FolderBrowserDialog, Multiselect, 多選資料夾, IFileOpenDialog, WinForms, net8.0-windows, 資料夾選擇
- Created-at: 2026-08-07
- Related: feedback-未實證先別斷言-從根源驗證-先證再修-反退避反冗長

## 知識

- [固] `FolderBrowserDialog.Multiselect` / `SelectedPaths` 是 **.NET 9** 才加入的 API；net8.0-windows 編譯直接 CS1061 失敗。動手前先確認專案 TargetFramework。
- [固] 不升 TargetFramework（避免連動部署端 runtime 需求）時，解法是 COM interop 呼叫 Windows Vista+ `IFileOpenDialog`，options = `FOS_PICKFOLDERS(0x20) | FOS_FORCEFILESYSTEM(0x40) | FOS_ALLOWMULTISELECT(0x200)`；結果走 `GetResults` → `IShellItemArray` → `GetDisplayName(SIGDN_FILESYSPATH=0x80058000)`。
- [固] interop 介面的 **vtable 順序必須完整**（IModalWindow → IFileDialog → IFileOpenDialog）；用不到的方法可宣告成無參數佔位，但一個都不能少，否則呼叫到錯的 slot。
- [固] 使用者取消 = `Show()` 回傳 HRESULT `0x800704C7`（ERROR_CANCELLED），要當正常路徑處理，不能拋例外。
- [固] interop 失敗需 fallback 回單選 FolderBrowserDialog，且**降級必須出訊號**，否則使用者只會覺得「多選壞了」但查不出原因。
- [固] 實例：FastSVNViewer `UI/MultiFolderPicker.cs`。

## 行動

- 寫 WinForms 資料夾多選前先看 csproj TargetFramework：net9+ 直接用 Multiselect，net8 以下走 IFileOpenDialog interop
- COM interop 完成後務必人工點一次驗證，編譯過不代表 vtable 對

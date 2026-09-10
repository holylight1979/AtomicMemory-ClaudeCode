# dotnet pack 在 GeneratePackageOnBuild 專案不重建-nuspec 新版號包舊 dll

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: dotnet pack, nupkg, GeneratePackageOnBuild, NU5026, 版號, AssemblyVersion, pack 舊 dll, nuspec
- Created-at: 2026-09-07

## 知識

- [臨] 2026-09-07 實測（SDK 10.0.400、csproj 有 `GeneratePackageOnBuild=true` + `IncludeSymbols` + `snupkg`）：改完 `<Version>` 後直接 `dotnet pack -c Release -o X` **不會重新編譯**——bin 裡有舊 dll 就照包（nuspec 版號是新的、dll AssemblyVersion 仍是舊的）；bin 清掉再 pack 則報 NU5026 找不到 dll。
- [臨] 正確流程：`dotnet build <csproj> -c Release`（GeneratePackageOnBuild 會在 bin/Release 直接產 nupkg+snupkg）→ 需要另存再 `dotnet pack -c Release --no-build -o <目錄>`。
- [臨] 包完一律用反射驗 dll 內版號與新成員（PowerShell `[Reflection.Assembly]::LoadFile(dll)`，讀 `GetName().Version` 與 `AssemblyInformationalVersionAttribute`），不能只看 nuspec；nuspec `<repository commit>` 是 HEAD，工作樹髒也照寫，正式包要 commit 後重 pack。

## 行動

- 改版號後產包：先 dotnet build -c Release，再 pack --no-build
- 交付 nupkg 前反射驗 dll 版號與新成員

# dotnet run 單檔跑拋棄式 demo (.NET 10 file-based app)

- Scope: global
- Author: holylight
- Confidence: [觀]
- Trigger: dotnet run 單檔, file-based app, C# 單檔, 拋棄式 demo, C# script, 驗證 C# 語意
- Created-at: 2026-06-10

## 知識

- [觀] .NET 10 SDK 支援 file-based app：`dotnet run path\to\foo.cs` 直接編譯+執行**單一 .cs 檔**（免建 .csproj）。注意是 `dotnet run foo.cs`，**不是** `dotnet run --project foo.cs`（後者把 .cs 當專案檔→報 MSB4025）。檔內可用 top-level statements，型別宣告（如 `static class`）放檔尾；可 `return int` 當 exit code。適合寫拋棄式單元/語意實證 demo，跑完即刪。

## 行動

- 要快速驗證一段 C# 邏輯/語意又不想建專案 → 寫單一 .cs（top-level statements）用 `dotnet run foo.cs`（.NET 10+），跑完刪除。

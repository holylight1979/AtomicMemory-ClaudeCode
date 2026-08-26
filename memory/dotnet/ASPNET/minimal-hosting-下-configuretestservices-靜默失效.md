# minimal hosting 下 ConfigureTestServices 靜默失效

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: ConfigureTestServices, WebApplicationFactory, TestServer, ConfigureWebHostBuilder, GenericWebHostBuilder, minimal hosting, UseTestServer, builder.WebHost, 測試 override 沒生效, ASP.NET Core 整合測試
- Created-at: 2026-08-07

## 知識

- [臨] `Microsoft.AspNetCore.TestHost` 的 `ConfigureTestServices(this IWebHostBuilder, ...)` 內部用**型別名字串比對**分流：只有 `GetType().Name == "GenericWebHostBuilder"` 時才轉呼叫 `ConfigureServices`；否則改註冊 `IStartupConfigureServicesFilter`。
- [臨] minimal hosting（`WebApplication.CreateBuilder`）的 `builder.WebHost` 實際型別是 **`ConfigureWebHostBuilder`**，而 minimal hosting **不消費** 上述 startup filter。結果：override **完全不生效且不報錯**——測試名照樣綠，斷言卻在跑 production 註冊。（已由獨立探針專案實測：marker count=1、resolved 為 production 實作）
- [臨] `WebApplicationFactory<T>` 能用 `ConfigureTestServices`，是因為它經 `DeferredHostBuilder.ConfigureWebHost` 拿到的是真正的 `GenericWebHostBuilder`。一旦自建 test host 改用 `builder.WebHost`，這個前提就消失。
- [臨] 自建 test host 時覆寫改用 `IWebHostBuilder.ConfigureServices`：`ConfigureWebHostBuilder.ConfigureServices` 立即作用在 `builder.Services` 本身（`ReferenceEquals` 實測為真），因此 `RemoveAll<T>()` + `AddSingleton<T>()` 照常生效，且後註冊者勝。
- [臨] 測試 seam 要放在**全部 production 註冊之後、`builder.Build()` 之前**——這是「override 後註冊而生效」與「無人能繞過 production 註冊自建 composition」同時成立的唯一位置。
- [臨] `WebApplication.CreateBuilder(args)` 確實接受 `--environment` / `--applicationName` / `--contentRoot` 並寫進 host configuration（實測）；命令列排在 `ASPNETCORE_*` 環境變數之後，會蓋過 process-wide 污染。
- [臨] `UseTestServer()` 只是 `ConfigureServices` 加 `AddSingleton<IServer, TestServer>()`；Kestrel 的 `IServer` 在 `WebApplicationBuilder` 建構時就註冊了，後註冊的 TestServer 因 last-wins 勝出。

## 行動

- 同步阻塞啟動 host 用 `Task.Run(op).GetAwaiter().GetResult()`，不要直接在測試執行緒上 `.GetAwaiter().GetResult()`——前者讓 await 在 thread pool 續行、避開測試 runner 的 SynchronizationContext，且單一例外會原型別重擲（不包 AggregateException），精確型別斷言仍成立
- 判斷「測試 override 到底有沒有生效」不能只看測試綠：加一條會因 override 而改變結果的斷言，或直接斷言 `services` 解析出來的實作型別
- 自建 test host 取代 `WebApplicationFactory` 時，順手斷言 host identity（environment / applicationName / contentRoot）真的抵達 host configuration，否則註解會說謊

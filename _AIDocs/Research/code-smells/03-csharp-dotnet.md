# 切面 03：C# / .NET 語言與執行期特有的壞味道

> 閱讀樹：[README.md](README.md)（分類樹、症狀路由、重疊對照）｜全條目一句話索引：[00-index.md](00-index.md)

> 用途：給日後 LLM／審查者查「這段 C# 算不算壞味道、為何、怎麼修、工具能否自動抓」。
> 查證日：2026-10-08。規則編號全部實際查過：CA 查 dotnet/docs 原始檔、S 查 SonarSource/sonar-dotnet 的 rspec/cs 原檔、RCS 查 Roslynator 的 Analyzers.xml 與官方文件站、VSTHRD 查 vs-threading 文件索引、UNT 查 Microsoft.Unity.Analyzers 文件索引、SA 查 StyleCopAnalyzers 文件。查不到可靠來源的內容標為「未查證」，自己推論出來的標為「推論」。
> 條目編號（A01、B03…）方便交叉引用，標題格式是 `### 編號 英文名（中文譯名）`。

---

## 0. 工具圖例與規則連結格式

| 前綴 | 工具 | 規則說明連結格式 | 備註 |
|---|---|---|---|
| CS#### | C# 編譯器 | https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-messages/ | 不必另外安裝 |
| CA#### | .NET SDK 內建的 Microsoft.CodeAnalysis.NetAnalyzers | https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/caXXXX | **很多規則在 .NET 10 預設沒有啟用**（條目裡會標示），要靠 `<AnalysisMode>`（例如 `All`、`Recommended`）、`<AnalysisLevel>latest-Recommended</AnalysisLevel>` 或 .editorconfig 打開 |
| IDE#### | .NET 程式碼樣式分析 | https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/style-rules/ideXXXX | |
| S#### | SonarAnalyzer.CSharp | https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/SXXXX.html | rules.sonarsource.com 這次從查證環境連不上，所以改引 GitHub 上的 rspec 原檔 |
| RCS#### | Roslynator | https://josefpihrt.github.io/docs/roslynator/analyzers/RCSXXXX | 有些規則預設停用（條目裡會標示） |
| VSTHRD### | Microsoft.VisualStudio.Threading.Analyzers | https://microsoft.github.io/vs-threading/analyzers/VSTHRDXXX.html | 非 Visual Studio 擴充套件的專案也能用 |
| UNT#### / USP#### | Microsoft.Unity.Analyzers | https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/UNTXXXX.md | Unity 專用；USP 開頭的是「抑制器」，專門消掉一般規則在 Unity 裡的誤報 |
| SA#### | StyleCop.Analyzers | https://github.com/DotNetAnalyzers/StyleCopAnalyzers/blob/master/documentation/SAXXXX.md | |
| RS0030 | Microsoft.CodeAnalysis.BannedApiAnalyzers | https://github.com/dotnet/roslyn-analyzers/blob/main/src/Microsoft.CodeAnalysis.BannedApiAnalyzers/BannedApiAnalyzers.Help.md | 用自訂的 `BannedSymbols.txt` 禁用專案不准用的 API（例如 Unity 的 `GameObject.Find`）。RS0030 這個編號是從第三方 SSW 規則頁查到的 |

CA 規則的預設狀態來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/overview

---

## 1. 這個切面的分類架構

```
C# / .NET 特有壞味道
├─ A. 非同步與 Task（async/await）      死結、執行緒池飢餓、例外不見、取消斷鏈
├─ B. 資源與生命週期                     GC 只管記憶體，不管 socket/handle/訂閱關係/DI 生命週期
├─ C. 例外處理                           吞掉、毀掉堆疊、把例外當 if 用、在不該拋的地方拋
├─ D. 集合與 LINQ                        延遲執行被重跑、O(n²)、走訪時修改、外洩可變集合
├─ E. 型別與記憶體配置                   boxing、字串、struct、閉包、params、反射、dynamic
├─ F. 語言構件與設計濫用                 partial/region/擴充方法/static/欄位可見性/繼承/參數/null/魔術字串
├─ G. 執行緒與同步                       鎖的對象、雙重檢查、非執行緒安全集合、Timer、鎖的粒度
└─ H. Unity C# 特有                      每幀成本、Unity 物件的 null 語意、協程、物件池
```

- **A 非同步**：C# 伺服器與 client 最常見的執行期事故來源。訊號多半 grep 得到（`.Result`、`async void`），也有大量 analyzer。
- **B 資源**：判準是「誰擁有、誰釋放、誰活得比誰久」。洩漏往往來自生命週期不對稱，不是忘了 `new`。
- **C 例外**：讓錯誤看不見，或讓錯誤訊息失真。
- **D 集合/LINQ**：可讀性好的寫法放錯位置（熱路徑、迴圈內）就變成效能或正確性問題。
- **E 配置**：在每幀、每封包、每個 tick 跑的程式碼上，「小配置」會累積成 GC 卡頓。
- **F 構件濫用**：語言功能被拿來掩蓋設計問題（partial 藏巨型類別、region 藏長方法）。
- **G 執行緒**：鎖錯對象、自己寫的延遲初始化、多執行緒共寫集合。
- **H Unity**：Unity 物件的生命週期與 null 語意和一般 C# 不同，加上每幀呼叫的成本模型。

---

## A. 非同步與 Task

### A01 Async Void Method（async void 方法）
- 定義：不是事件處理器的 async 方法，卻宣告成回傳 `void`。
- 辨識訊號：grep `async void`，而且簽章不是 `(object sender, XxxEventArgs e)`；介面或基底類別的 `void` 方法被 override 成 async。
- 為何有害：呼叫端拿不到 Task，無法 await，也不知道何時完成。方法內沒處理的例外會直接拋到開始時的 SynchronizationContext，外層 try/catch 抓不到，常常直接讓程序崩潰。這種方法也很難寫單元測試。
- 解法：改成回傳 `Task`。真正的事件處理器保留 `async void`，但本體只寫 `await HandleXxxAsync()`，邏輯放進可以測試的 `async Task` 方法，並在處理器裡 try/catch 記錄。
- 何時不算：事件處理器，包括「邏輯上的」事件處理器，例如 `ICommand.Execute`。
- 工具規則：S3168、VSTHRD100。
- 範例：
```csharp
// 壞
public async void SaveAsync() { await _repo.WriteAsync(); }
// 好
public async Task SaveAsync() { await _repo.WriteAsync(); }
```
- 來源：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md ；https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming ；https://learn.microsoft.com/en-us/dotnet/csharp/asynchronous-programming/async-return-types

### A02 Async Lambda Passed as Void Delegate（async lambda 被轉成 async void 委派）
- 定義：把 async lambda 傳給參數型別是 `Action`、`Action<T>`、`TimerCallback` 這類回傳 void 的委派，結果等於寫了一個看不見的 async void。
- 辨識訊號：`list.ForEach(async x => ...)`、`Parallel.ForEach(src, async x => ...)`、`new Timer(async _ => ...)`、自訂的 `FireAndForget(Action a)` 收到 `async () => ...`。
- 為何有害：A01 的問題全部繼承。呼叫端以為工作已經做完（例如 `ForEach` 回傳時存檔其實還沒寫完）；Timer 回呼裡的例外會讓程序崩潰。
- 解法：API 加一個 `Func<Task>` 多載；改用 `foreach + await` 或 `await Task.WhenAll(...)`；週期性工作改用 .NET 6+ 的 `PeriodicTimer`，或在 Timer 回呼裡寫 `_ = TickAsync();`，並讓 `TickAsync` 自己 try/catch 記錄。
- 何時不算：委派型別本身就是 `Func<Task>`，例如 `Task.Run(async () => ...)`。
- 工具規則：VSTHRD101。
- 範例：
```csharp
// 壞
players.ForEach(async p => await SaveAsync(p));
// 好
foreach (var p in players) await SaveAsync(p);
```
- 來源：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md （Timer callbacks／Implicit async void delegates 兩節）；https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming

### A03 Sync-over-Async（同步阻塞等待非同步：.Result / .Wait() / GetAwaiter().GetResult()）
- 定義：在同步程式碼裡用 `.Result`、`.Wait()`、`.GetAwaiter().GetResult()`、`Task.WaitAll/WaitAny` 卡住等 Task 完成。
- 辨識訊號：grep `\.Result\b|\.Wait\(\)|GetAwaiter\(\)\.GetResult\(\)|Task\.WaitAll|Task\.WaitAny`。
- 為何有害：
  1. 在「一次只跑一段程式」的 SynchronizationContext 上會死結（WinForms、WPF、舊版 ASP.NET）。await 完要回原 context 繼續執行，但那個 context 的執行緒正卡著在等它，兩邊互等。Unity 在主執行緒裝了 `UnitySynchronizationContext`，Task 的續行預設會回主執行緒，所以在主執行緒上 `.Result` 等這種 Task 也會死結。Unity 文件沒有直接寫「會死結」，這是依機制推論。
  2. 在伺服器上一個請求同時占兩條執行緒，量大時執行緒池飢餓，回應時間暴增。
  3. `.Wait()`／`.Result` 會把例外包成 AggregateException，錯誤處理變複雜。
- 解法：一路 async 到底，改到入口為止（事件處理器、controller action、`async Task Main`）。建構子或 DI 工廠裡的非同步初始化改用靜態 async factory（見 A13）。
- 何時不算：C# 7.1 之前的 Console `Main`（S4462 也排除 Main）；先檢查 `IsCompleted` 確定 Task 已完成再取 `Result`（CA1849 允許抑制）；接在 `Task.Run`／`StartNew` 後面的阻塞不會死結（S4462 會排除），但仍然占一條執行緒。
- 工具規則：S4462、VSTHRD002、CA1849（只在 async 方法內觸發；.NET 10 預設未啟用）。
- 範例：
```csharp
// 壞
var data = client.GetStringAsync(url).Result;
// 好
var data = await client.GetStringAsync(url);
```
- 來源：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md ；https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming ；https://learn.microsoft.com/en-us/aspnet/core/fundamentals/best-practices ；https://learn.microsoft.com/en-us/dotnet/core/diagnostics/debug-threadpool-starvation ；https://devblogs.microsoft.com/dotnet/should-i-expose-synchronous-wrappers-for-asynchronous-methods/ ；https://docs.unity3d.com/Manual/async-awaitable-continuations.html

### A04 Blocking Call Inside Async Method（async 方法裡呼叫阻塞 API）
- 定義：async 方法裡呼叫 `Thread.Sleep`、同步 I/O（`File.ReadAllText`、`Stream.Read`），或任何已有 Async 版本卻呼叫同步版本的 API。
- 辨識訊號：async 方法內出現 `Thread.Sleep(`；呼叫 `Xxx()`，而同一型別有 `XxxAsync()`。
- 為何有害：方法簽章看起來是非同步，繼續執行後卻卡住當下的執行緒。在 UI 或遊戲主執行緒上畫面會卡；在伺服器上會占住請求執行緒。
- 解法：`await Task.Delay(...)`、`await XxxAsync(...)`。Cleary 的對照表：Wait/Result 改 await，WaitAny 改 WhenAny，WaitAll 改 WhenAll，Thread.Sleep 改 Task.Delay。
- 何時不算：同一方法內明確分成同步、非同步兩條路徑；或已檢查 Task 已完成（CA1849 的抑制條件）。
- 工具規則：CA1849、VSTHRD103、S6966、S4462（async 方法內的 `Thread.Sleep` 會報，非 async 方法內的不報）。
- 範例：
```csharp
// 壞
async Task TickAsync() { Thread.Sleep(100); await SendAsync(); }
// 好
async Task TickAsync(CancellationToken ct) { await Task.Delay(100, ct); await SendAsync(ct); }
```
- 來源：https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming （Figure 5）；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1849 ；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S4462.html

### A05 Async-over-Sync（用 Task.Run 包同步方法，假裝非同步）
- 定義：對外提供 `XxxAsync() => Task.Run(() => Xxx())`；在 ASP.NET Core 裡 `await Task.Run(...)` 後立刻等待；或用 `Task.Run` 回傳一個早就算好的值。
- 辨識訊號：方法本體只有 `return Task.Run(...)`；controller 或 handler 裡出現 `await Task.Run(() => SyncCall())`；`Task.Run(() => a + b)`。
- 為何有害：沒有省下任何執行緒，只是換一條執行緒來卡，還多了排程成本。呼叫端會誤以為這個 API 能擴展。ASP.NET Core 的程式本來就跑在 thread pool 上，再 Task.Run 只是多排一次程，也擋不住阻塞。
- 解法：函式庫只提供同步版本，要不要 Task.Run 由呼叫端決定；已知結果用 `Task.FromResult` 或 `ValueTask`；真正的 I/O 改用真的非同步 API。
- 何時不算：客戶端（UI、遊戲 client）把 CPU 密集計算移出 UI 或主執行緒。learn 的 async scenarios 明確建議 CPU-bound 工作用 Task.Run。背景執行緒能不能呼叫某個引擎 API 要另外確認（Unity 這部分未查證）。
- 工具規則：未查到專用的 analyzer 規則。
- 範例：
```csharp
// 壞
public Task<int> SumAsync(int a, int b) => Task.Run(() => a + b);
// 好
public Task<int> SumAsync(int a, int b) => Task.FromResult(a + b);
```
- 來源：https://devblogs.microsoft.com/dotnet/should-i-expose-asynchronous-wrappers-for-synchronous-methods/ ；https://learn.microsoft.com/en-us/aspnet/core/fundamentals/best-practices ；https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md ；https://learn.microsoft.com/en-us/dotnet/csharp/asynchronous-programming/async-scenarios

### A06 Long-Running Blocking Loop on Thread Pool（長時間阻塞迴圈占住執行緒池）
- 定義：把永遠不結束、會阻塞的處理迴圈丟給 `Task.Run`，例如佇列消費或同步收封包的迴圈。
- 辨識訊號：`Task.Run(() => { while (true) { queue.Take(); ... } })`。
- 為何有害：thread pool 的執行緒設計上是短暫借用的，被永久占住時 pool 必須補新執行緒，造成飢餓與延遲。
- 解法：開一條專用的 `Thread { IsBackground = true }`；或用 `TaskCreationOptions.LongRunning`。迴圈裡如果是真的非同步 I/O，就改寫成 async 迴圈。
- 何時不算：迴圈每一輪都在 await 真的非同步操作，執行緒在 await 期間會還給 pool（推論）。
- 工具規則：未查到。
- 範例：
```csharp
// 壞
Task.Run(ProcessQueue);   // ProcessQueue 內是 while(true) + 阻塞 Take()
// 好
new Thread(ProcessQueue) { IsBackground = true }.Start();
```
- 來源：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md （Avoid using Task.Run for long running work that blocks the thread）

### A07 Unobserved Fire-and-Forget Task（射後不理、沒人觀察的 Task）
- 定義：呼叫回傳 Task 的方法後，不 await、不保存，也不處理它的結果或例外。
- 辨識訊號：async 方法內出現 CS4014 警告；同步方法內直接呼叫 `DoAsync();`；寫了 `_ = DoAsync();`，但 `DoAsync` 裡沒有 try/catch。
- 為何有害：例外被默默吞掉；呼叫端在操作完成前就繼續往下跑，造成順序與正確性 bug（CS4014 文件原意）。傳進去的 IDisposable 可能在 Task 還沒用完前就被釋放（CA2025）。
- 解法：能 await 就 await。確定要在背景跑，就交給有生命週期管理與例外記錄的背景服務或佇列；至少讓被呼叫的 async 方法自己 try/catch 並記錄。
- 何時不算：刻意用 `_ =` 丟棄，而且被呼叫端保證會處理並記錄所有例外。
- 工具規則：CS4014（只在 async 方法內）、VSTHRD110（補足同步方法內的情況）、CA2025（.NET 10 預設未啟用）。
- 範例：
```csharp
// 壞
void OnLogin(Player p) { _audit.WriteAsync(p.Id); }
// 好
async Task OnLoginAsync(Player p) { await _audit.WriteAsync(p.Id); }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-messages/async-await-errors ；https://microsoft.github.io/vs-threading/analyzers/VSTHRD110.html ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2025

### A08 Missing or Unforwarded CancellationToken（沒有或沒往下傳 CancellationToken）
- 定義：async API 不接受 CancellationToken；或接受了卻沒傳給下游的 async 呼叫；或 `CancellationTokenSource` 用完沒 Dispose。
- 辨識訊號：方法參數有 `ct`，但呼叫 `ReadAsync(buf)`、`QueryAsync(sql)` 時沒傳；token 不是最後一個參數；`new CancellationTokenSource(timeout)` 沒包 `using`。
- 為何有害：取消是「合作式」的，鏈上有一處沒傳，整條就無法取消。例如玩家斷線了，伺服器還在跑他的查詢。帶 timeout 的 CTS 沒 Dispose，計時器會一直留著。
- 解法：公開 async API 的最後一個參數放 `CancellationToken ct = default`，一路往下傳；`using var cts = ...`；要檢查取消就用 `ct.ThrowIfCancellationRequested()`。
- 何時不算：操作本身不能取消而且很短；刻意不讓它被取消的收尾流程，例如存檔的最終提交（實務判斷）。
- 工具規則：CA2016（有 token 卻沒往下傳；.NET 10 預設 suggestion）、CA1068（token 要放最後一個參數）、CA2250（改用 ThrowIfCancellationRequested）。
- 範例：
```csharp
// 壞
async Task<Item[]> LoadAsync(CancellationToken ct) => await _db.QueryAsync(sql);
// 好
async Task<Item[]> LoadAsync(CancellationToken ct) => await _db.QueryAsync(sql, ct);
```
- 來源：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md （Cancelling／Always dispose CancellationTokenSource 兩節）；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2016 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1068

### A09 ConfigureAwait Misuse（ConfigureAwait 用錯場合）
- 定義：兩個方向都算壞味道：(a) 通用函式庫沒用 `ConfigureAwait(false)`；(b) 應用層程式（UI 事件、需要回主執行緒的遊戲邏輯）用了 `ConfigureAwait(false)` 之後，又去操作 UI 或主執行緒限定的物件。另一種是只在第一個 await 加。
- 辨識訊號：函式庫專案的 await 沒加 ConfigureAwait；UI handler 或 MonoBehaviour 裡 `.ConfigureAwait(false)` 之後接著操作控制項或 Unity 物件；同一方法只有第一個 await 加了。
- 為何有害：(a) 函式庫可能被「有 SynchronizationContext 又同步阻塞」的呼叫端使用，結果死結或效能變差；(b) 續行會跑在 thread pool 上，存取 UI 或主執行緒限定 API 會出錯。只加第一個 await 沒用：如果那個 Task 在 await 時已經完成，執行緒就不會切換，後面的 await 仍會抓到原 context。
- 解法：通用函式庫每個 await 都加 `ConfigureAwait(false)`；應用層程式不要加。ASP.NET Core 沒有 SynchronizationContext，加不加行為都一樣。Unity 遊戲碼屬於應用層，而 UnitySynchronizationContext 會讓續行回主執行緒，所以不該加（依 Toub FAQ 的原則推論）。
- 何時不算：ASP.NET Core 應用程式碼；Console app。
- 工具規則：CA2007（針對函式庫；.NET 10 預設未啟用。官方文件明講應用程式碼應關掉這條規則，可以用 `output_kind` 只套用在 DLL）、S3216（只針對 .NET Framework 函式庫）、VSTHRD111、RCS1090。
- 範例：
```csharp
// 壞（UI／遊戲主執行緒程式碼）
await LoadAsync().ConfigureAwait(false); label.text = "done";
// 好（通用函式庫）
var n = await stream.ReadAsync(buf, ct).ConfigureAwait(false);
```
- 來源：https://devblogs.microsoft.com/dotnet/configureawait-faq/ ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2007 ；https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming ；https://docs.unity3d.com/Manual/async-awaitable-continuations.html

### A10 ValueTask / Awaitable Consumed More Than Once（ValueTask／Awaitable 被重複使用）
- 定義：對同一個 `ValueTask` await 兩次以上；還沒完成就取 `.Result`；存進欄位稍後再用；或多處同時 await。Unity 的 `Awaitable` 屬於同一類：官方文件明講 await 超過一次是不安全的。
- 辨識訊號：`ValueTask` 被指派到區域變數或欄位，然後被 await 兩次。
- 為何有害：ValueTask 背後可能是會被池化重用的來源物件，第二次使用可能拿到別人的結果、拋例外或資料損毀。Unity Awaitable 是池化物件，重複 await 可能拋例外或死結。
- 解法：直接 `await Foo()`；需要多次使用時，呼叫一次 `.AsTask()`，之後重用那個 Task。
- 何時不算：實作是你自己控制的，而且確定它只是包一個 Task（CA2012 的抑制條件）。
- 工具規則：CA2012（.NET 10 預設 suggestion）、S5034。
- 範例：
```csharp
// 壞
var vt = GetAsync(); var a = await vt; var b = await vt;
// 好
var t = GetAsync().AsTask(); var a = await t; var b = await t;
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2012 ；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S5034.html ；https://docs.unity3d.com/Manual/async-awaitable-introduction.html

### A11 Returning Task Without Await Inside using/try（在 using／try 裡直接 return Task）
- 定義：沒有 async 修飾的 Task 方法，在 `using` 或 `try` 區塊內直接 `return SomethingAsync();`。
- 辨識訊號：非 async 的 Task 方法裡出現 `using (...) { return xxxAsync(...); }`，或 `try { return xxxAsync(); } catch ...`。
- 為何有害：方法一回傳，using 就把資源 Dispose 了，但 Task 可能還在用它。try/catch 只包住「啟動」，沒包住「完成」，所以抓不到非同步例外，堆疊資訊也比較差。
- 解法：加上 `async`，改成 `return await`。
- 何時不算：單純轉發、外面沒有 using/try/lock 的一行包裝。這時 RCS1174 與 VSTHRD202 反而建議拿掉多餘的 async。Fowler 傾向一律 async/await，讓例外語意一致、比較好診斷；兩派依熱路徑的效能需求取捨。
- 工具規則：RCS1229。
- 範例：
```csharp
// 壞
Task<Data> GetAsync() { using var c = Open(); return c.ReadAsync(); }
// 好
async Task<Data> GetAsync() { using var c = Open(); return await c.ReadAsync(); }
```
- 來源：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md （Prefer async/await over directly returning Task）；https://josefpihrt.github.io/docs/roslynator/analyzers/RCS1229

### A12 Returning Null from Task-Returning Method（Task 方法回傳 null）
- 定義：回傳 `Task`／`Task<T>` 的「非 async」方法 `return null;`。
- 辨識訊號：沒有 async 修飾的 Task 方法裡有 `return null;`。
- 為何有害：呼叫端 `await` 一個 null，會拋 NullReferenceException。
- 解法：`return Task.CompletedTask;`、`return Task.FromResult<T>(default);`。
- 何時不算：async 方法裡的 `return null;` 是 `Task<T>` 的結果值，不算。
- 工具規則：S4586、RCS1210、VSTHRD114。
- 範例：
```csharp
// 壞
Task SaveAsync() { if (!_dirty) return null; return WriteAsync(); }
// 好
Task SaveAsync() { if (!_dirty) return Task.CompletedTask; return WriteAsync(); }
```
- 來源：https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S4586.html ；https://microsoft.github.io/vs-threading/analyzers/VSTHRD114.html

### A13 Blocking Async Initialization in Constructor（建構子裡同步等待非同步初始化）
- 定義：建構子或 DI 工廠 lambda 用 `.Result`／`.Wait()` 等待非同步初始化。
- 辨識訊號：建構子內有 `.Result`、`.GetAwaiter().GetResult()`；`services.AddSingleton(sp => CreateAsync(sp).Result)`。
- 為何有害：建構子不能 async，同步等待就是 sync-over-async（A03）。官方 DI 指南把「async DI 工廠會死結」列為反模式。
- 解法：改用靜態 `CreateAsync` 工廠方法；或建構完再呼叫 `InitializeAsync`。在 DI 裡先同步解析服務，非同步工作放到之後的 async 方法。
- 何時不算：無。
- 工具規則：S4462、VSTHRD002（抓 `.Result`／`.Wait` 本身）。
- 範例：
```csharp
// 壞
public Conn(IFactory f) { _c = f.ConnectAsync().Result; }
// 好
public static async Task<Conn> CreateAsync(IFactory f) => new Conn(await f.ConnectAsync());
```
- 來源：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md （Constructors）；https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines （Async DI factories can cause deadlocks）

### A14 TaskCompletionSource Without RunContinuationsAsynchronously（TCS 沒有指定續行非同步執行）
- 定義：`new TaskCompletionSource<T>()` 沒帶 `TaskCreationOptions.RunContinuationsAsynchronously`。
- 辨識訊號：grep `new TaskCompletionSource` 卻沒有該選項。
- 為何有害：呼叫 `SetResult` 的那條執行緒會當場執行所有 await 這個 Task 的續行。如果它手上持有鎖，就可能在鎖內跑外部程式碼，造成死結、執行緒池飢餓，或讓 SetResult 的呼叫端被意外卡住。
- 解法：建構時傳入 `TaskCreationOptions.RunContinuationsAsynchronously`。注意是 TaskCreationOptions，不是 TaskContinuationOptions，傳錯會被 CA2247 抓到。
- 何時不算：極度效能敏感、續行很短，而且已評估過同步續行的風險（推論）。
- 工具規則：CA2247 只抓「傳錯列舉型別」；漏傳這件事本身沒查到規則。
- 範例：
```csharp
// 壞
var tcs = new TaskCompletionSource<Packet>();
// 好
var tcs = new TaskCompletionSource<Packet>(TaskCreationOptions.RunContinuationsAsynchronously);
```
- 來源：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/

### A15 Lock Around Await / Unsynchronized Async State（用 lock 保護非同步臨界區／非同步狀態沒同步）
- 定義：在 async 程式碼裡用 `lock` 或 `Monitor` 保護跨越 await 的臨界區。`lock` 裡不能 await（編譯不過），所以有人改寫手動 Monitor，或把 await 移到鎖外造成競態。另一種是以為「async 只有一條執行緒就不用同步」，結果出現「讀取、await、寫回」的競態。
- 辨識訊號：`Monitor.Enter` 與 `Monitor.Exit` 之間夾著 await；`_value = await NextAsync(_value);` 可能被並行呼叫。
- 為何有害：Monitor 的鎖屬於取得它的那條執行緒，await 之後可能換到別的執行緒繼續，就沒辦法正確釋放（依 Monitor 的擁有權語意推論，未逐字查證）。「讀取、await、寫回」在 await 期間，狀態可能已被別人改掉。
- 解法：`SemaphoreSlim(1, 1)`，搭配 `await WaitAsync()` 與 `try/finally { Release(); }`。不跨 await 的同步臨界區，在 .NET 9+ 用 `System.Threading.Lock`。
- 何時不算：臨界區內沒有 await。
- 工具規則：CS1996（lock 內 await 是編譯錯誤）、S7133（鎖應在同一個方法內釋放）。
- 範例：
```csharp
// 壞
lock (_gate) { _cache = await LoadAsync(); }   // CS1996 編譯錯誤，常被改寫成更糟的 Monitor 版本
// 好
await _sem.WaitAsync(ct); try { _cache = await LoadAsync(); } finally { _sem.Release(); }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/statements/lock ；https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming （Figure 10）；https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-messages/async-await-errors

### A16 Deferred Argument Validation in Async Method（async 方法的參數檢查延後才拋出）
- 定義：async 方法開頭的參數檢查（例如 ArgumentNullException）位在 async 狀態機裡面，例外會被存進 Task，等到 await 才出現。
- 辨識訊號：`public async Task X(T arg) { ArgumentNullException.ThrowIfNull(arg); await ...; }`。
- 為何有害：錯誤延後到離呼叫點很遠的地方才爆；如果沒人 await，甚至永遠不會出現。
- 解法：外層用非 async 方法同步驗證參數，再呼叫內部的 async 本體（local function）。
- 何時不算：private 或 internal 方法，而且所有呼叫端都會立刻 await。這時 Fowler「統一用 async/await 讓例外語意一致」的建議比較划算。
- 工具規則：S4457。
- 範例：
```csharp
// 壞
public async Task SendAsync(Packet p) { ArgumentNullException.ThrowIfNull(p); await _sock.SendAsync(p.Bytes); }
// 好
public Task SendAsync(Packet p) { ArgumentNullException.ThrowIfNull(p); return Core(); async Task Core() => await _sock.SendAsync(p.Bytes); }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices-for-exceptions （Throw argument validation exceptions synchronously）；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S4457.html

---

## B. 資源與生命週期

### B01 Undisposed IDisposable（IDisposable 沒有釋放）
- 定義：建立了 IDisposable 物件（檔案、socket、DB 連線、CancellationTokenSource、Timer…），卻沒有在每一條路徑上 Dispose。
- 辨識訊號：`File.OpenRead(`、`new SqlConnection(` 等沒有包在 `using` 裡；例外路徑沒有釋放。
- 為何有害：非受控資源（handle、socket、連線）要等 finalizer 才釋放，甚至永遠不釋放。結果是資源耗盡、檔案被鎖住、連線池用光。
- 解法：`using var x = ...;` 或 `await using`；所有權轉移時，明確寫出由誰負責釋放。
- 何時不算：從 DI 容器拿到的服務，由容器負責釋放，接收者不該 Dispose；刻意長期重用的 HttpClient（B06）；所有權已交給會負責釋放的包裝物件。
- 工具規則：CA2000（.NET 10 預設未啟用）、S2930、CA2025。
- 範例：
```csharp
// 壞
var fs = File.OpenRead(path); var b = fs.ReadByte();
// 好
using var fs = File.OpenRead(path); var b = fs.ReadByte();
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2000 ；https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/implementing-dispose ；https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines （Disposal of services）

### B02 Disposable Field Owner Not Disposable（擁有 disposable 欄位卻不實作或不傳遞 Dispose）
- 定義：類別持有 IDisposable 欄位，自己卻不實作 IDisposable；或實作了，但 Dispose 漏掉某個欄位，或沒呼叫基底類別的 Dispose。
- 辨識訊號：欄位型別實作了 IDisposable，類別本身沒有 Dispose；Dispose 方法裡少了某個欄位；子類別的 `Dispose(bool)` 沒有 `base.Dispose(disposing)`。
- 為何有害：外部沒辦法釋放它內部的資源，子類別的資源也會洩漏。
- 解法：類別實作 IDisposable，在 Dispose 中釋放自己擁有的欄位；子類別 override `Dispose(bool)` 並呼叫 base。
- 何時不算：欄位是外部注入的，所有權不屬於這個類別。DI 指南：收到 IDisposable 依賴的類別，不需要因此自己實作 IDisposable。
- 工具規則：CA1001、CA2213、CA2215（三條在 .NET 10 預設都未啟用）、S2931、S2952。
- 範例：
```csharp
// 壞
class Session { readonly MemoryStream _buf = new(); }
// 好
sealed class Session : IDisposable { readonly MemoryStream _buf = new(); public void Dispose() => _buf.Dispose(); }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1001 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2213 ；https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines

### B03 Broken Dispose Pattern（Dispose 模式寫錯）
- 定義：IDisposable 的實作不符合模式：Dispose 重複呼叫會拋例外（不是冪等）；finalizer 路徑（`disposing == false`）去碰受控物件；沒呼叫 `GC.SuppressFinalize`；重複實作 IDisposable；自創其他 Dispose 多載；方法叫 Dispose 卻沒有實作介面。
- 辨識訊號：Dispose 裡沒有 `_disposed` 判斷；`Dispose(false)` 分支存取其他受控物件；類別有 `public void Dispose()` 卻沒有 `: IDisposable`。
- 為何有害：重複 Dispose 會拋例外。GC 執行 finalizer 的順序不確定，finalizer 期間可能存取到已被回收的物件。沒實作介面就不能用 using。
- 解法：sealed 類別只要一個簡單的 `Dispose()`；非 sealed 類別照標準的 `Dispose(bool)` 模式寫；Dispose 要能重複呼叫；受控資源只在 `disposing == true` 時釋放。
- 何時不算：無。
- 工具規則：CA1063（預設未啟用）、CA1816（預設 suggestion）、S3881、S3966（重複 Dispose）、S3234、S2953。
- 範例：
```csharp
// 壞
public void Dispose() { _conn.Close(); _conn = null; }   // 第二次呼叫就 NRE
// 好
public void Dispose() { if (_disposed) return; _disposed = true; _conn.Dispose(); }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/implementing-dispose ；https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/dispose-pattern

### B04 Unnecessary Finalizer（不必要的 finalizer／解構子）
- 定義：類別宣告了 `~ClassName()`，但沒有直接持有非受控資源，finalizer 裡只是計數、清欄位、寫 log、呼叫其他受控物件的 Dispose；或 finalizer 是空的。
- 辨識訊號：grep `~[A-Z]\w*\(\)`；finalizer 裡只有 `Interlocked.Decrement`、`= null`、`Log(...)`。
- 為何有害：有 finalizer 的實例一建立就登記到終結佇列（finalization queue）。回收它至少要兩次 GC：第一次只能排進「等待執行 finalizer」，第二次才真正釋放。這段期間它引用的整個物件圖都被延長壽命。空的或無用的 finalizer 純粹是效能損失。
- 解法：直接刪掉。真的要包非受控 handle，用 `SafeHandle` 的衍生類別，自己不寫 finalizer。只為除錯計數而寫的 finalizer，先 grep 確認計數器沒人讀，再連同計數器一起刪掉。
- 何時不算：直接持有 IntPtr 等非受控資源，而且沒辦法用 SafeHandle 包裝。
- 工具規則：CA1821（空 finalizer；預設 suggestion）。RCS1106 已標為 Obsolete。
- 範例：
```csharp
// 壞
~Monster() { s_instanceCount--; }
// 好
// 刪掉 finalizer；真的要統計，就在明確的 Despawn/Dispose 路徑裡計數
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/classes-and-structs/finalizers （Empty finalizers should not be used）；https://learn.microsoft.com/en-us/dotnet/api/system.object.finalize （requires at least two garbage collections）；https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/dispose-pattern （AVOID making types finalizable）

### B05 Event Subscription Leak（事件訂閱了沒退訂：有 += 沒有 -=，含 static 事件）
- 定義：用 `+=` 訂閱事件後，沒在對應時機 `-=` 退訂，而事件來源比訂閱者活得久。常見的長壽來源：static 事件、單例管理器、全域事件匯流排、長壽的連線物件。
- 辨識訊號：`+=` 與 `-=` 數量不對稱；有 static event；用 lambda 訂閱（`x.Changed += (s, e) => ...`）卻沒保存委派，所以根本退不掉；Unity 在 OnEnable 訂閱，卻沒在 OnDisable 或 OnDestroy 退訂。
- 為何有害：`source.Event += handler` 讓來源強參考著訂閱者。只要來源還活著，訂閱者連同它引用的整個物件圖（UI、場景物件）都不會被 GC，就是記憶體洩漏。已經「死掉」的物件還會繼續收到事件、執行邏輯（推論；常見症狀是 NullReference 或 MissingReference）。
- 解法：訂閱與退訂成對（建構對 Dispose、OnEnable 對 OnDisable）；訂閱時回傳 IDisposable token；真的掌握不了退訂時機，才用 weak event 模式。
- 何時不算：來源和訂閱者同時生死，或來源比訂閱者短命，例如物件訂閱自己子物件的事件。
- 工具規則：沒查到直接偵測這種洩漏的 CA/S/RCS 規則。相關規則：S3172（委派相減可能出錯）。
- 範例：
```csharp
// 壞
void OnEnable() { GameEvents.ScoreChanged += s => label.text = s.ToString(); }
// 好
void OnEnable() => GameEvents.ScoreChanged += OnScore;
void OnDisable() => GameEvents.ScoreChanged -= OnScore;
```
- 來源：https://learn.microsoft.com/en-us/dotnet/desktop/wpf/events/weak-event-patterns （Why implement the weak event pattern?）

### B06 HttpClient Per Request（每次請求都 new 一個 HttpClient）
- 定義：每次發請求都 `new HttpClient()`，通常還包在 using 裡。
- 辨識訊號：會被頻繁呼叫的方法裡有 `using var client = new HttpClient()`。
- 為何有害：每個 HttpClient 實例有自己的連線池。連線關閉後，TCP 埠會停在 TIME_WAIT 一段時間，請求量高時會把可用的埠用光（port／socket exhaustion）。反過來，永久的單例 HttpClient 又會忽略 DNS 變更。
- 解法：.NET Core／.NET 5+ 用 static 或單例的 HttpClient，搭配 `SocketsHttpHandler { PooledConnectionLifetime = ... }`；或用 IHttpClientFactory（typed client）。.NET Framework 用 IHttpClientFactory。
- 何時不算：少數幾個長壽實例，例如為了不同 proxy 或不同 cookie 容器，官方明說可以。
- 工具規則：S6962（ASP.NET Core 熱路徑）。
- 範例：
```csharp
// 壞
using var http = new HttpClient(); var s = await http.GetStringAsync(url);
// 好
static readonly HttpClient s_http = new(new SocketsHttpHandler { PooledConnectionLifetime = TimeSpan.FromMinutes(2) });
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/networking/http/httpclient-guidelines ；https://learn.microsoft.com/en-us/aspnet/core/fundamentals/best-practices

### B07 Closure-Extended Lifetime（閉包捕捉延長物件壽命）
- 定義：lambda 或匿名方法捕捉了 `this` 或大型區域變數，又被交給更長壽的東西（static 快取、事件、計時器、背景工作），被捕捉的物件因此無法回收。
- 辨識訊號：lambda 裡用到實例成員或大物件，而這個 lambda 被存進 static 欄位、事件、Timer 或長壽的 Task。
- 為何有害：官方文件：被捕捉的變數要等引用它的委派可以被回收時，才會被回收。
- 解法：縮小捕捉範圍，只捕捉需要的值，不要捕捉整個 this 或整個大物件；用 C# 9 的 `static` lambda 讓編譯器禁止捕捉；用 state 參數傳入；確保委派本身會被移除。
- 何時不算：委派的壽命不超過被捕捉的物件。
- 工具規則：沒查到直接規則。`static` lambda 是語言層的防線。
- 範例：
```csharp
// 壞：閉包捕捉整個 bigData，委派活多久它就活多久
var bigData = LoadAll(); s_jobs.Add(() => Log(bigData.Length));
// 好：只捕捉需要的值
int len = bigData.Length; s_jobs.Add(() => Log(len));
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/lambda-expressions （Capture of outer variables；static lambda）

### B08 Captive Dependency / Container-Captured Transient（DI 生命週期錯配）
- 定義：DI 生命週期配錯。singleton 依賴 scoped 或 transient 服務，短命服務被「俘虜」成單例；transient 的 IDisposable 從根容器解析，被容器一直抓著；在 scope 外解析 scoped 服務。
- 辨識訊號：`AddSingleton<T>` 的建構子參數裡有 scoped 服務（例如 DbContext）；在根容器上反覆呼叫 `app.Services.GetService<某個 transient disposable>()`。
- 為何有害：短命服務被長期持有，狀態會跨請求外洩，還有執行緒安全問題。容器會一直抓著 transient disposable，直到容器本身釋放，就是記憶體洩漏。
- 解法：打開 scope validation（`validateScopes: true`）；長壽服務透過 `IServiceScopeFactory.CreateScope()` 取得短命服務；transient disposable 改用工廠模式，自己管理生命週期。
- 何時不算：無。
- 工具規則：靠執行期的 scope validation（拋 InvalidOperationException："Cannot consume scoped service ... from singleton ..."）。沒查到靜態分析規則。
- 範例：
```csharp
// 壞
services.AddSingleton<Matchmaker>();   // Matchmaker(GameDbContext db)，而 DbContext 是 scoped
// 好
public Matchmaker(IServiceScopeFactory f) => _f = f;   // 要用時才 using var s = _f.CreateScope();
```
- 來源：https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines （Captive dependency／Disposable transient services captured by container）；https://blog.ploeh.dk/2014/06/02/captive-dependency/

### B09 Explicit GC.Collect（手動呼叫 GC.Collect）
- 定義：程式裡主動呼叫 `GC.Collect()`，或 `GC.GetTotalMemory(true)`（它內部會呼叫 GC.Collect）。
- 辨識訊號：grep `GC.Collect`、`GetTotalMemory(true)`。
- 為何有害：強迫做一次完整的追蹤式回收，可能要暫停所有執行緒；多數情況下成本遠大於好處。
- 解法：刪掉，用 profiler 找出真正產生配置的地方。
- 何時不算：Sonar 明列的例外：某個一次性事件之後，大量長壽物件同時死亡。例如切換場景、讀取畫面（這個對應是推論）。
- 工具規則：S1215。
- 範例：
```csharp
// 壞
void Update() { if (++_frame % 600 == 0) GC.Collect(); }
// 好
// 刪掉；用 profiler 找出每幀的配置並消除
```
- 來源：https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S1215.html

---

## C. 例外處理

### C01 Catch-All Exception（catch (Exception) 一網打盡）
- 定義：在一般流程裡用 `catch (Exception)`、`catch (SystemException)` 或不帶型別的 `catch` 處理例外。
- 辨識訊號：grep `catch \(Exception`、`catch \(SystemException`，以及後面直接接區塊的 `catch`。
- 為何有害：連不該處理的例外也一起吞下或處理錯（程式錯誤、取消、資源耗盡），把真正的問題藏起來，除錯變困難。官方原則：無法復原的例外就不要抓。
- 解法：只抓能處理的具體型別。需要合併處理時用例外篩選，例如 `catch (Exception e) when (e is IOException or TimeoutException)`。一定要抓一般例外時，最後一行 `throw;`。
- 何時不算：程式邊界的「最後防線」，例如主迴圈、請求管線、執行緒或 Task 的入口、async void 事件處理器。在這些地方抓住、完整記錄，讓單一請求或單一 frame 失敗，而不是整個程序崩潰。這是實務判斷：CA1031 文件本身寫「不要抑制」，用的時候要明確註記理由。
- 工具規則：CA1031（.NET 10 預設未啟用）、S2221。
- 範例：
```csharp
// 壞
try { Load(path); } catch (Exception) { UseDefaults(); }
// 好
try { Load(path); } catch (FileNotFoundException) { UseDefaults(); }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1031 ；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S2221.html ；https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices-for-exceptions

### C02 Swallowed Exception / Empty Catch（空 catch、吞掉例外）
- 定義：catch 區塊是空的，或只有註解或 `return`，不記錄、不處理、也不重拋。
- 辨識訊號：`catch { }`、`catch (Exception) { }`、`catch (Exception e) { /* ignore */ }`。
- 為何有害：錯誤默默消失，系統在錯誤狀態下繼續運作。降級或失敗沒有留下任何訊號。
- 解法：至少記錄，而且把例外物件帶進 log；或縮小 try 範圍、改抓具體型別。確定可以忽略時，寫明原因，並只忽略那個具體型別。
- 何時不算：刻意忽略的、具體且預期中的例外，例如關閉時的 `OperationCanceledException`，並附註解說明。
- 工具規則：S2486（只報「抓一般例外的空 catch」，裡面有註解就不算空，所以 `// ignore` 能騙過工具，但壞味道還在）、S108、RCS1075、S6667（catch 裡寫 log 要把例外物件傳進去）。
- 範例：
```csharp
// 壞
try { Save(); } catch { }
// 好
try { Save(); } catch (IOException ex) { _log.LogError(ex, "Save failed"); throw; }
```
- 來源：https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S2486.html ；https://josefpihrt.github.io/docs/roslynator/analyzers/RCS1075

### C03 throw ex Resets Stack Trace（throw ex 毀掉堆疊追蹤）
- 定義：在 catch 裡用 `throw ex;` 重拋原本的例外。
- 辨識訊號：`catch (... ex) { ...; throw ex; }`。
- 為何有害：堆疊追蹤從目前這個方法重新開始，原本拋出的位置和中間的呼叫鏈全部遺失。
- 解法：在 catch 內用 `throw;`；要在 catch 外重拋，用 `ExceptionDispatchInfo.Capture(e)` 先存起來，之後 `.Throw()`；要包裝成別的例外，就 `throw new XxxException("...", ex)`，保留 InnerException。
- 何時不算：刻意包成新的例外，而且帶了 inner exception。
- 工具規則：CA2200（.NET 10 預設 warning）、S3445、RCS1044。
- 範例：
```csharp
// 壞
catch (IOException ex) { Log(ex); throw ex; }
// 好
catch (IOException ex) { Log(ex); throw; }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices-for-exceptions （Capture and rethrow exceptions properly）；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2200

### C04 Useless Rethrow Catch（只做重拋的 catch）
- 定義：catch 區塊裡只有 `throw;`，其他什麼都沒做。
- 辨識訊號：`catch (...) { throw; }`。
- 為何有害：純雜訊，還會讓讀者以為這裡有處理。
- 解法：拿掉 try/catch。
- 何時不算：有多個 catch，刻意讓某個子型別直接重拋，避開後面較一般的 catch（推論）。
- 工具規則：S2737、RCS1265。
- 範例：
```csharp
// 壞
try { Run(); } catch (Exception) { throw; }
// 好
Run();
```
- 來源：https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S2737.html ；https://josefpihrt.github.io/docs/roslynator/analyzers/RCS1265

### C05 Exceptions as Control Flow（把例外當流程控制）
- 定義：用 try/catch 處理「平常就會發生」的情況，例如用 `int.Parse` 加 catch 判斷輸入是不是數字，或用 KeyNotFoundException 判斷字典裡有沒有這個鍵。
- 辨識訊號：catch 裡是正常的分支邏輯（回傳預設值、改走另一條路）；熱路徑上用 try/catch 包 Parse 或索引子。
- 為何有害：拋例外很昂貴。設計準則明講不要把例外當正常流程。在每幀、每封包這種熱路徑上特別傷效能。
- 解法：Tester-Doer 模式（先檢查再做），或 Try-Parse 模式（`TryParse`、`TryGetValue`）。自家 API 也提供 TryXxx 版本。
- 何時不算：真正罕見的錯誤，例如檔案突然消失、網路中斷。
- 工具規則：沒查到直接規則。CA1854（ContainsKey 加索引子）間接相關。
- 範例：
```csharp
// 壞
int lv; try { lv = int.Parse(s); } catch (FormatException) { lv = 1; }
// 好
if (!int.TryParse(s, out var lv)) lv = 1;
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/exception-throwing （DO NOT use exceptions for the normal flow of control, if possible）；https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/exceptions-and-performance ；https://learn.microsoft.com/en-us/aspnet/core/fundamentals/best-practices

### C06 Throwing from finally / Dispose / Unexpected Members（在 finally、Dispose 等不該拋的地方拋例外）
- 定義：在不預期會拋例外的位置拋例外：finally、例外篩選、Dispose、ToString、Equals、GetHashCode、靜態建構子、事件存取子、隱式轉型運算子。
- 辨識訊號：`finally { ... throw ... }`；`public void Dispose() { ... throw ... }`；`override string ToString()` 裡有 throw。
- 為何有害：finally 裡拋例外會蓋掉正在傳遞的原始例外；Dispose 拋例外會中斷 using 的清理鏈；Equals 或 GetHashCode 拋例外會讓集合壞掉。
- 解法：在這些位置吞下並記錄，或改用狀態回報。Dispose 只有在程序狀態已經毀損的極端情況才拋。
- 何時不算：`NotImplementedException`（S3877 排除）；事件存取子拋 ArgumentException、InvalidOperationException、NotSupportedException（S3877 排除）。
- 工具規則：CA2219（.NET 10 預設 suggestion）、CA1065、S1163、S3877。
- 範例：
```csharp
// 壞
finally { _conn.Close(); if (_dirty) throw new InvalidOperationException(); }
// 好
finally { _conn.Close(); }   // 狀態檢查移到 finally 外面
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices-for-exceptions （Don't raise exceptions in finally clauses／from unexpected places）；https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/dispose-pattern ；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S3877.html

### C07 Catching NullReferenceException / Throwing Reserved Types（抓 NullReferenceException、拋保留例外型別）
- 定義：用 `catch (NullReferenceException)` 來處理 null；或自己 `throw new Exception()`，或拋 `NullReferenceException`、`IndexOutOfRangeException` 這類保留給執行期的型別。
- 辨識訊號：grep `catch \(NullReferenceException`、`throw new Exception\(`、`throw new NullReferenceException`。
- 為何有害：NullReferenceException 是程式錯誤的症狀，應該修正 null 的來源，而不是攔截它。拋一般的 Exception 會逼呼叫端只能 catch 全部（C01）。
- 解法：事先檢查 null，或啟用 NRT（見 F10）；拋具體型別（ArgumentNullException、InvalidOperationException 等）或自訂例外。
- 何時不算：無。
- 工具規則：S1696、CA2201（預設未啟用）。
- 範例：
```csharp
// 壞
try { name = player.Profile.Name; } catch (NullReferenceException) { name = "?"; }
// 好（Profile 不是 UnityEngine.Object 時；是的話見 H09）
name = player.Profile?.Name ?? "?";
```
- 來源：https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S1696.html ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2201 ；https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices-for-exceptions

---

## D. 集合與 LINQ

### D01 Multiple Enumeration of IEnumerable（同一個 IEnumerable 被列舉多次）
- 定義：同一個 `IEnumerable<T>` 被列舉好幾次，尤其是延遲執行的 LINQ 或 DB 查詢。例如先 `Count()` 再 `foreach`，或先 `Any()` 再 `First()`。
- 辨識訊號：同一個區域變數或參數上，先後出現兩次以上的列舉操作（`Count()`、`Any()`、`First()`、`foreach`）。
- 為何有害：每列舉一次，就把整條查詢重跑一次，結果不會被快取。查詢很貴（DB、檔案）時效能變差；查詢有副作用時會產生 bug。
- 解法：要用好幾次，就先 `ToList()` 或 `ToArray()` 一次；參數型別改用 `IReadOnlyCollection<T>` 或 `IReadOnlyList<T>`，表明「已經物化」。
- 何時不算：確定底層就是 List 或陣列（CA1851 文件：可以轉成實際型別）。
- 工具規則：CA1851（.NET 10 預設未啟用）。
- 範例：
```csharp
// 壞
var alive = mobs.Where(m => m.Hp > 0); if (alive.Any()) Attack(alive.First());
// 好
var alive = mobs.Where(m => m.Hp > 0).ToList(); if (alive.Count > 0) Attack(alive[0]);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1851

### D02 Count() for Emptiness / LINQ on Sized Collections（用 Count() 判空、對有大小的集合呼叫 LINQ）
- 定義：用 `Count() > 0` 判斷 IEnumerable 是不是空的；或對本來就有 `Count`／`Length` 屬性的集合呼叫 LINQ 的 `Count()`、`Any()`。
- 辨識訊號：`.Count() > 0`、`.Count() == 0`；List 或陣列上呼叫 `.Any()`、`.Count()`。
- 為何有害：在一般 IEnumerable 上，`Count()` 要走完整個序列才知道結果；對 List 或陣列呼叫 LINQ 擴充方法，多了介面呼叫和型別檢查的成本。
- 解法：IEnumerable 判空用 `Any()`；List、陣列、一般集合用 `.Count`、`.Length` 或 `IsEmpty`。
- 何時不算：無。
- 工具規則：CA1827、CA1829、CA1860、CA1836（以上 .NET 10 預設都是 suggestion）、S1155、RCS1080。
- 範例：
```csharp
// 壞
if (list.Any()) Fire();   if (seq.Count() > 0) Fire();
// 好
if (list.Count > 0) Fire();   if (seq.Any()) Fire();
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1827 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1829 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1860

### D03 LINQ in Hot Path（熱路徑上用 LINQ）
- 定義：在每幀、每封包、每個伺服器 tick 都會執行的熱路徑上，使用 Where、Select、OrderBy、ToList 這類 LINQ 鏈。
- 辨識訊號：Update、FixedUpdate、伺服器 tick、封包處理器裡出現 `.Where(`、`.Select(`、`.OrderBy(`。
- 為何有害：每次呼叫通常都會配置委派、閉包（捕捉外部變數時）與列舉器物件。透過介面列舉也會配置；第三方實測：在 Unity 裡透過 `IEnumerable<T>` 介面 foreach，每次迴圈產生 40 bytes 垃圾。Unity 的 GC 不是世代式的，小配置累積起來就是 GC 尖峰。說明：「熱路徑避免 LINQ」是依這些機制得出的推論，不是哪一條官方條文；其中每個機制都有來源。
- 解法：熱路徑改寫成手動 for/foreach；預先配置暫存 List 並重用；用集合本身的方法（`List.Find`、`Exists`、`TrueForAll`、索引）取代 LINQ 擴充方法。
- 何時不算：冷路徑，例如初始化、編輯器工具、低頻的管理介面，LINQ 的可讀性比較好。
- 工具規則：S6602、S6603、S6605、S6608、S6617、RCS1077。Unity 專案可以用 RS0030 自訂禁止特定組件使用 System.Linq。
- 範例：
```csharp
// 壞（每幀執行）
void Update() { _target = enemies.Where(e => e.Alive).OrderBy(e => e.Dist).FirstOrDefault(); }
// 好
void Update() { Enemy best = null; foreach (var e in enemies) if (e.Alive && (best == null || e.Dist < best.Dist)) best = e; _target = best; }
```
- 來源：https://docs.unity3d.com/Manual/performance-reference-types.html （closures）；https://jacksondunstan.com/articles/3805 ；https://learn.microsoft.com/en-us/aspnet/core/fundamentals/best-practices （hot code paths）；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S6608.html

### D04 ToList/ToArray Abuse（ToList()／ToArray() 濫用）
- 定義：在查詢鏈中間呼叫 ToList() 或 ToArray()；只為了 foreach 就先物化；或寫出 `.ToList().Count()`、`.ToList().ForEach(...)`。
- 辨識訊號：`.ToList().Where(`、`.ToList().Count()`、`foreach (var x in q.ToList())`。
- 為何有害：多一次完整的配置與複製；破壞延遲執行與後續最佳化。例如 Entity Framework 會因此把後面的條件改成在記憶體裡做。
- 解法：直接列舉。需要在 client 端評估時，EF 用 `AsEnumerable()`（S2971 的說明）。真的需要快照才物化。
- 何時不算：需要快照的時候：走訪時要修改來源集合、要交給別的執行緒、要避免多次列舉（D01）、要避免延遲執行讀到之後才變動的資料。
- 工具規則：S2971（規則說明：不要在查詢鏈中間呼叫 ToArray() 或 ToList()）。
- 範例：
```csharp
// 壞
foreach (var p in players.Where(p => p.Online).ToList()) Notify(p);
// 好
foreach (var p in players.Where(p => p.Online)) Notify(p);
```
- 來源：https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S2971.html

### D05 Linear Lookup in Loop（迴圈裡做線性搜尋，變成 O(n²)）
- 定義：在迴圈裡對 List 或陣列呼叫 `Contains`、`IndexOf`、`Find`，總成本變成 O(n×m)，甚至 O(n²)。
- 辨識訊號：`foreach (...) if (list.Contains(x))`；`Where(x => otherList.Contains(x))`。
- 為何有害：`List<T>.Contains` 是線性搜尋，O(n)；`HashSet<T>.Contains` 是 O(1)。
- 解法：先建一個 HashSet 或 Dictionary 當索引，再查。
- 何時不算：集合很小（只有幾個元素），而且不在熱路徑上（推論）。
- 工具規則：沒查到直接規則。CA1868 是 Set 相關的規則。
- 範例：
```csharp
// 壞
var hits = items.Where(i => bannedIds.Contains(i.Id));   // bannedIds 是 List<int>
// 好
var banned = bannedIds.ToHashSet(); var hits = items.Where(i => banned.Contains(i.Id));
```
- 來源：https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.list-1.contains ；https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.hashset-1.contains

### D06 Double Dictionary Lookup（ContainsKey 加索引子，查兩次）
- 定義：`if (d.ContainsKey(k)) v = d[k];`、`if (!d.ContainsKey(k)) d.Add(k, v);`、`d.Keys.Contains(k)`。
- 辨識訊號：ContainsKey 後面緊接著同一個鍵的索引子或 Add。
- 為何有害：同一個鍵雜湊、查找兩次；`Keys.Contains` 不一定走雜湊查找。
- 解法：`TryGetValue`、`TryAdd`、`ContainsKey`。
- 何時不算：無。
- 工具規則：CA1854、CA1864、CA1841、CA1853。
- 範例：
```csharp
// 壞
if (cache.ContainsKey(id)) return cache[id];
// 好
if (cache.TryGetValue(id, out var v)) return v;
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1854 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/

### D07 Modifying Collection During Enumeration（走訪集合時修改它）
- 定義：用 foreach 走訪集合的同時，對同一個集合 Add 或 Remove。
- 辨識訊號：`foreach (var x in list) { ... list.Remove(x) ... }`。比較隱蔽的情況：走訪時觸發的事件回呼間接修改了集合，例如走訪怪物清單時，怪物的死亡事件把自己從清單移除。
- 為何有害：集合一變更，列舉器就失效，下一次 MoveNext 會拋 InvalidOperationException。
- 解法：`list.RemoveAll(predicate)`；倒序 for 迴圈刪除；先收集要刪的項目，走訪完再處理；或走訪一份快照（`ToArray()`）。
- 何時不算：無。
- 工具規則：沒查到靜態規則，只會在執行期拋例外。
- 範例：
```csharp
// 壞
foreach (var m in mobs) if (m.Dead) mobs.Remove(m);
// 好
mobs.RemoveAll(m => m.Dead);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.list-1.getenumerator （An enumerator remains valid as long as the collection remains unchanged）

### D08 Exposing Mutable Collections（對外公開可變集合）
- 定義：公開 API 回傳或接收 `List<T>`；屬性回傳陣列；集合屬性有公開的 setter。
- 辨識訊號：`public List<T> Xxx { get; set; }`、`public T[] Xxx { get; }`。
- 為何有害：外部可以任意修改內部狀態，繞過不變量。屬性回傳陣列時，要嘛每次複製（有成本），要嘛不複製（不安全）。
- 解法：回傳 `IReadOnlyList<T>`、`IReadOnlyCollection<T>` 或 `ReadOnlyCollection<T>`；集合屬性設為唯讀；內部仍然用 List。
- 何時不算：internal 或 private 型別；為了序列化而需要 setter 的 DTO（推論）。
- 工具規則：CA1002、CA1819、CA2227（三條 .NET 10 預設都未啟用）、S2365、S3956、S4004。
- 範例：
```csharp
// 壞
public List<Item> Items { get; set; } = new();
// 好
private readonly List<Item> _items = new(); public IReadOnlyList<Item> Items => _items;
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1002 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1819 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2227

---

## E. 型別與記憶體配置

### E01 Boxing（裝箱）
- 定義：值型別被轉成 object 或介面型別時，會在堆積上配置一份副本。
- 辨識訊號：值型別傳給 `object` 參數（`string.Format`、`Debug.Log(object)`）；放進非泛型集合（ArrayList、Hashtable）；值型別用 `+` 跟字串串接；`object o = 5`。
- 為何有害：每次裝箱都要配置新物件，拆箱也有成本。Unity 文件指出，裝箱是 Unity 專案中最常見的意外暫時配置來源之一；而 Unity 的 GC 不是世代式的，很難有效清掉這類又小又頻繁的配置。
- 解法：用泛型集合與泛型方法；值型別先 `.ToString()` 再串接。C# 10／.NET 6 起，字串內插改由 interpolated string handler 以泛型的 `AppendFormatted<T>` 附加，值型別不再裝箱。Unity 使用的 C# 版本與 BCL 是否支援 handler，未查證。
- 何時不算：冷路徑、一次性的程式碼。
- 工具規則：RCS1198（預設停用，要手動打開）。新版 Roslyn 是否已自動把 `string + int` 最佳化成不裝箱，未查證。
- 範例：
```csharp
// 壞
string s = "HP:" + hp;              // hp 為 int，舊式串接會裝箱
// 好
string s = "HP:" + hp.ToString();
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/types/boxing-and-unboxing （Performance）；https://docs.unity3d.com/Manual/performance-reference-types.html ；https://devblogs.microsoft.com/dotnet/string-interpolation-in-c-10-and-net-6/ ；https://josefpihrt.github.io/docs/roslynator/analyzers/RCS1198

### E02 String Concatenation in Loop（迴圈裡串接字串）
- 定義：在迴圈裡用 `+` 或 `+=` 累加字串。
- 辨識訊號：迴圈本體裡有 `s += ...`。
- 為何有害：字串是不可變的，每次串接都配置一個新字串，中間結果全部變成垃圾（"A"、"AB"、"ABC"…）。
- 解法：用 StringBuilder（可以重用，用完 Clear）；或 `string.Join`、`string.Concat`。UI 文字只在值變動時更新（Unity 文件的建議）。
- 何時不算：固定幾段、不在迴圈裡的串接（推論）。
- 工具規則：S1643。
- 範例：
```csharp
// 壞
string log = ""; foreach (var e in events) log += e.Name + ",";
// 好
var sb = new StringBuilder(); foreach (var e in events) sb.Append(e.Name).Append(',');
```
- 來源：https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S1643.html ；https://docs.unity3d.com/Manual/performance-reference-types.html ；https://learn.microsoft.com/en-us/dotnet/standard/base-types/stringbuilder

### E03 Large or Mutable Struct（過大或可變的 struct）
- 定義：struct 大於約 16 bytes、可變、或常常被裝箱；或者沒有覆寫 Equals。
- 辨識訊號：struct 有 public 可寫欄位或 setter；欄位很多；被當成 object 或介面使用。
- 為何有害：值型別在傳參數、回傳、讀屬性時都會隱性複製。可變 struct 讓「改到的是副本」這種 bug 很難發現；大 struct 每次複製都有成本。沒覆寫 Equals 的非 blittable struct，預設 Equals 用反射逐一比較欄位，很昂貴。
- 解法：struct 保持小且不可變（`readonly struct`）；大型 struct 用 `in` 或 `ref readonly` 傳遞；實作 `IEquatable<T>` 或覆寫 Equals；大而可變的資料改用 class。
- 何時不算：效能關鍵、刻意設計成可變的資料 struct（例如 ECS 元件），而且使用端都用 ref 存取（推論）。
- 工具規則：IDE0250（struct 可以標成 readonly）、CA1815（.NET 10 預設未啟用）、RCS1242（不要用唯讀參考傳遞非 readonly 的 struct）。
- 範例：
```csharp
// 壞：可變 struct，改到的是副本
var s = player.Stats; s.Hp -= 10;            // player.Stats 根本沒變
// 好：readonly record struct，用 with 產生新值再寫回
player.Stats = player.Stats with { Hp = player.Stats.Hp - 10 };
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/choosing-between-class-and-struct ；https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/struct （DO NOT define mutable value types）；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1815 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/style-rules/ide0250

### E04 Closure Allocation in Hot Path（熱路徑上的閉包配置）
- 定義：熱路徑上的 lambda 或匿名方法捕捉了外部變數，每執行一次就配置一次閉包物件與委派。
- 辨識訊號：Update 或 tick 裡出現 `list.Find(x => x.Id == id)`、`Invoke(() => ...)`、`StartCoroutine(Wait(() => ...))`。
- 為何有害：捕捉外部變數的匿名方法會被編譯成一個產生出來的類別，配置在堆積上。Unity 建議每幀執行的程式碼盡量避免閉包與匿名方法。
- 解法：改用不捕捉的 `static` lambda（C# 9）搭配 state 參數的多載；把委派快取在欄位；或改寫成手動迴圈。
- 何時不算：冷路徑。
- 工具規則：沒查到 CA/S/RCS 直接規則。
- 範例：
```csharp
// 壞（每幀配置一個閉包）
void Update() { var t = targets.Find(x => x.Id == _lockId); }
// 好
void Update() { Target t = null; foreach (var x in targets) if (x.Id == _lockId) { t = x; break; } }
```
- 來源：https://docs.unity3d.com/Manual/performance-reference-types.html ；https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/operators/lambda-expressions

### E05 Params Array Allocation（params 陣列配置）
- 定義：在熱路徑上呼叫 `params T[]` 方法，例如多參數的 `string.Format`、自訂的 `Log(params object[])`，每次呼叫都配置一個陣列；值型別還會順便裝箱。
- 辨識訊號：熱路徑上呼叫參數為 `params object[]` 的方法。
- 為何有害：每次呼叫都 new 一個陣列。Unity 文件建議避免 params。舊式 string.Format 超過三個參數就要走 `params object[]` 多載，每次都配置陣列。
- 解法：為少數參數提供專用多載（設計準則明列這招）；C# 13 起 params 可以宣告成 `ReadOnlySpan<T>` 等集合型別；字串格式化改用內插。
- 何時不算：冷路徑。
- 工具規則：沒查到。
- 範例：
```csharp
// 壞
static void Log(string fmt, params object[] args) { /*...*/ }   Log("{0} hit {1}", who, dmg);
// 好
static void Log<T1, T2>(string fmt, T1 a, T2 b) { /*...*/ }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/parameter-design （CONSIDER providing special overloads ... small number of arguments）；https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/keywords/method-parameters ；https://docs.unity3d.com/Manual/performance-reference-types.html ；https://devblogs.microsoft.com/dotnet/string-interpolation-in-c-10-and-net-6/

### E06 Repeated Empty/Constant Array Allocation（重複配置空陣列或常數陣列）
- 定義：寫 `new T[0]`；或每次呼叫都傳一個新的常數陣列，例如 `new[] { ',', ';' }`。
- 辨識訊號：grep `new \w+\[0\]`；方法引數裡出現 `new[] { 常值... }`。
- 為何有害：每次執行都多一次沒必要的配置。
- 解法：用 `Array.Empty<T>()` 或 `[]`；常數陣列提出來放在 `static readonly` 欄位。
- 何時不算：無。
- 工具規則：CA1825、CA1861（.NET 10 預設都是 suggestion）。
- 範例：
```csharp
// 壞
var parts = line.Split(new[] { ',', ';' });
// 好
static readonly char[] s_seps = { ',', ';' };   var parts = line.Split(s_seps);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1825 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1861 ；https://docs.unity3d.com/Manual/performance-optimizing-arrays.html

### E07 Reflection in Hot Path（熱路徑上用反射）
- 定義：執行期反覆用 `GetType().GetMethod/GetField`、`Activator.CreateInstance`、`Assembly.GetTypes()` 來做分派或序列化。
- 辨識訊號：Update 或封包處理裡有 `System.Reflection`、`.Invoke(`；Unity 用字串方法名的 `SendMessage`、`Invoke("Name")`。
- 為何有害：反射慢，而且繞過編譯期檢查。Unity 的 Mono 與 IL2CPP 會快取所有 System.Reflection 物件，而且不回收，GC 只好一直掃描它們。
- 解法：啟動時建好委派或字典分派表，執行期只查表；在編輯器期間掃描並把結果序列化；或用程式碼產生（source generator）。
- 何時不算：啟動期或工具期的一次性掃描。
- 工具規則：UNT0018（Unity 效能關鍵訊息裡使用 System.Reflection）、S3011（用反射提高存取層級）。.NET 端沒查到效能類規則。
- 範例：
```csharp
// 壞
handler.GetType().GetMethod("On" + msg.Type).Invoke(handler, new object[] { msg });
// 好
s_handlers[msg.Type](handler, msg);   // 啟動時建好 Dictionary<MsgType, Action<Handler, Msg>>
```
- 來源：https://docs.unity3d.com/Manual/performance-gc-avoid-reflection.html ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/index.md

### E08 Dynamic Abuse（濫用 dynamic）
- 定義：明明型別已知，卻用 `dynamic` 取代介面、泛型或模式比對。
- 辨識訊號：grep `dynamic `，而且用在非 interop 的情境。
- 為何有害：繞過靜態型別檢查，錯誤延到執行期才出現；多載解析也延到執行期進行。在 IL2CPP 等 AOT 平台上的相容性未查證。
- 解法：用介面、泛型、`switch` 模式比對，或強型別的反序列化。
- 何時不算：COM interop、與動態語言互通，這是官方設計的用途。
- 工具規則：沒查到。
- 範例：
```csharp
// 壞
dynamic cfg = Load(); int hp = cfg.player.hp;     // 欄位拼錯要到執行期才爆
// 好
var cfg = JsonSerializer.Deserialize<GameConfig>(json); int hp = cfg.Player.Hp;
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/advanced-topics/interop/using-type-dynamic

### E09 ToLower/ToUpper Comparison & Culture-Sensitive Compare（用 ToLower／ToUpper 比較字串、比較時沒指定 StringComparison）
- 定義：用 `a.ToLower() == b.ToLower()` 做不分大小寫的比較；或字串比較、搜尋時沒有指定 StringComparison，結果套用目前的文化設定。
- 辨識訊號：`.ToLower() ==`、`.ToUpper() ==`；沒帶 StringComparison 參數的 `string.Compare`、`StartsWith(string)`、`IndexOf(string)`。
- 為何有害：ToLower 和 ToUpper 每次都配置新字串（CA1862 文件）。依文化比較時，在不同的地區設定下結果可能不同（例如土耳其語的 i），造成難以重現的 bug。文化這部分是常見知識，CA1309／CA1310 的論述未逐字擷取。
- 解法：`string.Equals(a, b, StringComparison.OrdinalIgnoreCase)`；識別碼、鍵值、協定字串一律用 Ordinal。
- 何時不算：顯示給使用者看、需要依語系排序的文字。
- 工具規則：CA1862、CA1307、CA1309、CA1310、RCS1155。
- 範例：
```csharp
// 壞
if (cmd.ToLower() == "quit") Quit();
// 好
if (string.Equals(cmd, "quit", StringComparison.OrdinalIgnoreCase)) Quit();
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1862 ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1309

---

## F. 語言構件與設計濫用

### F01 Partial Class as Giant-Class Hider（用 partial class 切開巨型類別）
- 定義：一個職責過多的巨型類別，用 `partial` 拆成很多個檔案（例如 `GameClient.Network.cs`、`GameClient.UI.cs`…共 37 檔），而不是拆成多個類別。
- 辨識訊號：同一個類別的 partial 檔案很多，檔案之間共用大量私有欄位；檔名按「功能」切分，型別卻只有一個；不是產生碼卻用了 partial。
- 為何有害：partial 只是在編譯時把檔案合併，類別仍然只有一個：所有欄位對所有部分都可見，耦合一點也沒少，還是無法單獨測試。拆成多檔後，「類別太大」的訊號從單一檔案的行數上消失，Large Class 被偽裝起來。官方列出的 partial 用途是多人同時編輯、和自動產生的程式碼分開、source generator，並不是用來切分職責。說明：官方沒有明文禁止這種用法，「這是壞味道」是推論。
- 解法：依職責抽出獨立類別（例如 NetworkSession、InventoryService），用組合或注入取代；partial 只留給產生碼。
- 何時不算：設計工具或 source generator 產生的另一半；類別本身職責單一，只是把介面實作分到另一個檔案。
- 工具規則：沒查到直接規則。可以看類別層級的耦合與複雜度指標：CA1506（類別耦合過高）、CA1502、S1200。
- 範例：
```csharp
// 壞
public partial class GameClient { /* 網路 */ }   public partial class GameClient { /* UI */ }   // …共 37 檔
// 好
public sealed class GameClient { public GameClient(NetworkSession net, UiRouter ui, InventoryService inv) { /*...*/ } }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/classes-and-structs/partial-classes-and-methods ；https://refactoring.guru/smells/large-class

### F02 Region Hiding Code（用 #region 遮住程式碼）
- 定義：用 `#region` 把巨型類別或巨型方法折疊起來，或在方法本體裡用 region 分段。
- 辨識訊號：grep `#region`，尤其是出現在方法本體裡的。
- 為何有害：編輯器預設會把 region 摺起來，程式碼被藏住，長期下來容易做出錯誤的維護決策（StyleCop 規則說明的原意）。方法裡需要用 region 分段，代表這個方法太長了。
- 解法：把 region 裡的內容抽成方法或類別，然後刪掉 region。
- 何時不算：團隊規範允許在類別層級用 region 把成員分組（SA1124 是選用規則；推論）。
- 工具規則：SA1124（不要用 region）、SA1123（不要在元素本體內放 region）。
- 範例：
```csharp
// 壞（示意）
void Tick() {
    #region 移動
    /* 200 行 */
    #endregion
    #region 戰鬥
    /* 300 行 */
    #endregion
}
// 好
void Tick() { UpdateMovement(); UpdateCombat(); }
```
- 來源：https://github.com/DotNetAnalyzers/StyleCopAnalyzers/blob/master/documentation/SA1124.md ；https://github.com/DotNetAnalyzers/StyleCopAnalyzers/blob/master/documentation/SA1123.md

### F03 Extension Method Abuse（濫用擴充方法）
- 定義：自己有原始碼的型別，用擴充方法代替成員；對 object 或極廣泛的型別（string、int）加入領域邏輯的擴充；所有擴充方法都丟進一個叫 `Extensions` 的命名空間。
- 辨識訊號：`this` 參數是自家類別；`this object`；命名空間就叫 `Extensions`。
- 為何有害：邏輯散落各處，讀者找不到行為定義在哪裡。擴充方法的簽章如果和型別本身的成員相同，就永遠不會被呼叫。對 object 加擴充，會污染所有型別的自動完成清單。
- 解法：能改原型別就加成員，或用衍生類別、服務類別。擴充方法只用在不屬於你的型別，或介面的通用行為；命名空間以功能命名。
- 何時不算：LINQ 風格的介面擴充、流暢式（fluent）設定 API、為不屬於你的第三方型別補功能。
- 工具規則：S4225（不要擴充 object）、S4226（擴充方法放在獨立的命名空間）。
- 範例：
```csharp
// 壞
public static int CalcDamage(this Player p, Monster m) { /*...*/ }   // Player 是自家類別
// 好
public int CalcDamage(Monster m) { /*...*/ }   // 放進 Player，或抽成 DamageCalculator 服務
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/extension-methods （AVOID frivolously defining extension methods, especially on types you don't own）；https://learn.microsoft.com/en-us/dotnet/csharp/programming-guide/classes-and-structs/extension-methods （General Guidelines）

### F04 Mutable Static State（可變的 static 狀態）
- 定義：public 或 protected 的非 readonly static 欄位；實例方法寫入 static 欄位；用全域可變的 static 變數當共享狀態。
- 辨識訊號：`public static int X;`、`public static List<T> X = ...;`；實例方法裡有 `s_xxx = ...`。
- 為何有害：任何人、任何執行緒都能改，結果是競態、測試互相污染、程式行為依執行順序而定。伺服器上的 static 狀態由所有請求共享，很容易出執行緒 bug。
- 解法：把狀態封裝進實例，用 DI 傳遞；必要的 static 用 readonly 或 const；共享的計數用 Interlocked。
- 何時不算：const；static readonly 的不可變物件；有明確同步保護的快取。
- 工具規則：CA2211（.NET 10 預設 suggestion）、S2223、S2696、S2386、S3010。
- 範例：
```csharp
// 壞
public static int OnlineCount;   /* 多處 */ OnlineCount++;
// 好
private static int s_online; public static int OnlineCount => Volatile.Read(ref s_online);   /* 寫入 */ Interlocked.Increment(ref s_online);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2211 ；https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices （Avoid providing static methods that alter static state）；https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines

### F05 Singleton / Service Locator / Static Service Access（Singleton、Service Locator、從 static 取服務）
- 定義：用 `XxxManager.Instance` 這種全域單例存取一切；在類別內部呼叫 `GetService<T>()` 或 `Locator.Get<T>()` 取得依賴；把 IServiceProvider 存在 static 欄位。
- 辨識訊號：到處都是 `.Instance.`；建構子收 IServiceProvider，內部到處 GetService；有 static 的 IServiceProvider。
- 為何有害：依賴被藏起來，從建構子看不出這個類別需要什麼；少了什麼依賴，編譯期不知道，執行期才失敗；測試時難以替換。單例會把不相干的請求耦合在一起，長期抓著一大串物件，還得自己保證執行緒安全。
- 解法：建構子注入；單例的生命週期交給 DI 容器，不要寫 static Instance。真的需要延遲解析時，用明確的工廠介面；但官方也把「注入一個會在執行期解析依賴的工廠」視為 service locator 的變體，要節制。
- 何時不算：組合根（Composition Root，組裝所有依賴的入口）與框架的進入點。Unity 的 MonoBehaviour 無法用建構子注入，少量入口服務用單例可以接受（推論）。
- 工具規則：沒查到直接規則。
- 範例：
```csharp
// 壞
public void Buy(int id) { var inv = ServiceLocator.Get<IInventory>(); inv.Add(id); }
// 好
public Shop(IInventory inv) => _inv = inv;   public void Buy(int id) => _inv.Add(id);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines （Avoid using the service locator pattern／Avoid static access to services）；https://blog.ploeh.dk/2010/02/03/ServiceLocatorisanAnti-Pattern/

### F06 Public or Protected Fields（public 或 protected 欄位）
- 定義：不是 const、也不是 static readonly 的 public 或 protected 實例欄位。
- 辨識訊號：`public int hp;`、`protected List<T> items;`。
- 為何有害：以後想加驗證、變更通知或延遲計算時，沒辦法在不破壞相容性的前提下改；子類別和外部都能直接改內部狀態，沒有人守住不變量。
- 解法：私有欄位加屬性。Unity 需要序列化時，用 `[SerializeField] private`（Unity analyzers 的 USP0004／USP0006 專門替這種欄位消除誤報）。
- 何時不算：效能關鍵的純資料 struct，例如數學向量（推論）。
- 工具規則：CA1051（.NET 10 預設未啟用）、S1104、S2357。
- 範例：
```csharp
// 壞
public int hp;
// 好
[SerializeField] private int hp;   public int Hp => hp;
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/field （DO NOT provide instance fields that are public or protected）；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1051 ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/index.md

### F07 Deep Inheritance（繼承太深）
- 定義：類別的繼承層級太深。CA1501 的門檻是 5 層以上；預設排除 `System.*` 命名空間的型別，也可以設定排除其他命名空間。
- 辨識訊號：`class Boss : EliteMonster`、`EliteMonster : Monster`、`Monster : Character`、`Character : Entity`…一路往上。
- 為何有害：行為分散在好幾層 override 裡，想看懂一個方法就得讀完整條繼承鏈；改了基底類別，所有子類別都受影響（脆弱的基底類別）。
- 解法：優先用組合而不是繼承；用介面加元件化來拆分行為。
- 何時不算：框架本身帶來的層數（可以用 CA1501 的設定排除）。
- 工具規則：CA1501（.NET 10 預設未啟用）、S110。
- 範例：
```csharp
// 壞
class Boss : EliteMonster { }   // EliteMonster : Monster : Character : Entity : ...
// 好
sealed class Boss { readonly Health _hp; readonly AiBrain _ai; readonly SkillSet _skills; }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1501 ；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S110.html

### F08 Out/Ref Parameter Overuse & Long Parameter List（out／ref 參數太多、參數清單太長）
- 定義：方法用好幾個 out 或 ref 參數回傳多個結果，或參數數量太多。
- 辨識訊號：同一個簽章裡有 2 個以上的 out；ref 用在參考型別上；參數超過 7 個（S107 的預設門檻未查證）。
- 為何有害：呼叫端難讀，還得先宣告變數。ref 傳參考型別的語意很難懂（設計準則：DO NOT pass reference types by reference）。
- 解法：回傳 tuple、record 或結果物件；把參數包成參數物件。
- 何時不算：Try-Parse 模式的單一 out（設計準則推薦的用法）；效能關鍵時用 ref 或 in 傳大型 struct。
- 工具規則：CA1021、CA1045（兩條 .NET 10 預設都未啟用）、S3874、S107。
- 範例：
```csharp
// 壞
void Calc(int atk, out int dmg, out bool crit, out bool miss);
// 好
DamageResult Calc(int atk);   public readonly record struct DamageResult(int Dmg, bool Crit, bool Miss);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/parameter-design （AVOID using out or ref parameters）；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1021 ；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S3874.html

### F09 Boolean Flag Argument（用 bool 參數切換行為）
- 定義：用 bool 參數切換方法的行為，例如 `Save(true)`、`Spawn(pos, false, true)`。
- 辨識訊號：呼叫端出現沒有具名引數的 `true`／`false` 常值；方法內有 `if (flag) {...} else {...}`，兩邊做的是不同的事。
- 為何有害：呼叫端看不出 true 或 false 代表什麼；通常表示這個方法同時做兩件事；以後需要第三種狀態時，就得改簽章。
- 解法：拆成兩個意圖明確的方法（`SaveAndClose()`、`Save()`）；有兩個以上的 bool 時改用 enum（設計準則：DO use enums if a member would otherwise have two or more Boolean parameters）；或至少用具名引數。
- 何時不算：建構子中真正只有兩種狀態、只用來初始化某個 bool 屬性的參數（設計準則允許）。
- 工具規則：SonarAnalyzer C# 沒有對應規則（rspec/cs 底下沒有 S2301）；其他工具也沒查到。
- 範例：
```csharp
// 壞
Spawn(pos, true, false);
// 好
Spawn(pos, SpawnOptions.Elite);   // 或 SpawnElite(pos)
```
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/parameter-design （Choosing Between Enum and Boolean Parameters）；https://martinfowler.com/bliki/FlagArgument.html

### F10 Null Return Without Nullable Annotations（用 null 表示「沒有」，卻沒啟用 NRT）
- 定義：方法用 null 表示「空集合」或「沒有結果」，型別上卻看不出來；專案沒啟用 nullable reference types（NRT），哪些東西可能是 null 全靠註解或猜。
- 辨識訊號：回傳集合的方法裡有 `return null;`；csproj 裡沒有 `<Nullable>enable</Nullable>`；程式裡到處是防禦性的 null 檢查，或到處冒出 NullReferenceException。
- 為何有害：呼叫端忘記檢查就是 NullReferenceException；不知道哪些可能是 null，只好處處檢查，變成雜訊。啟用 NRT 後，編譯器會在編譯期提示可能的 null 解參考。
- 解法：回傳集合時，用空集合（`Array.Empty<T>()`、`[]`）代替 null；啟用 `<Nullable>enable</Nullable>`，可能為 null 的地方標成 `T?`；公開 API 入口用 `ArgumentNullException.ThrowIfNull`。
- 何時不算：`TryXxx(out T? value)` 模式；型別上明確標了 `T?` 的「找不到」語意。注意：UnityEngine.Object 的 null 語意比較特殊（見 H09），NRT 管不到「已銷毀但不是 null」的狀態（推論）。
- 工具規則：S1168、CA1062（.NET 10 預設未啟用）、S3900、啟用 NRT 後的編譯器 nullable 警告。
- 範例：
```csharp
// 壞
public List<Item> GetDrops() { if (!_dead) return null; /*...*/ }
// 好
public IReadOnlyList<Item> GetDrops() { if (!_dead) return Array.Empty<Item>(); /*...*/ }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/null-safety/nullable-reference-types ；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S1168.html ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1062

### F11 Magic Strings（魔術字串）
- 定義：程式裡散落著有特定意義的字串常值（事件名、設定鍵、場景名、tag、參數名），同一個字串在多處重複出現。
- 辨識訊號：同一個字串常值出現 3 次以上；`throw new ArgumentNullException("paramName")`；`LoadScene("Lobby")`。
- 為何有害：拼錯了編譯期抓不到；改名要全域搜尋取代；重複的常值很容易沒同步改到。
- 解法：用 `nameof(...)`；集中定義成 const 或 static readonly；改用 enum 或強型別 ID。Unity 特有的字串見 H03、H10。
- 何時不算：只出現一次、意思一看就懂的訊息文字。給使用者看的文案應該走本地化資源。
- 工具規則：CA1507（參數或屬性名改用 nameof；.NET 10 預設 suggestion）、S2302、S1192（重複的字串常值）、S109（魔術數字）。
- 範例：
```csharp
// 壞
throw new ArgumentNullException("playerId");   SceneManager.LoadScene("Lobby");
// 好
throw new ArgumentNullException(nameof(playerId));   SceneManager.LoadScene(SceneNames.Lobby);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1507 ；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S1192.html

### F12 Virtual Call in Constructor（建構子裡呼叫可覆寫的成員）
- 定義：建構子呼叫 virtual 或 abstract 成員。
- 辨識訊號：建構子本體裡呼叫標了 virtual、abstract 或 override 的成員。
- 為何有害：衍生類別的 override 會在衍生類別的建構子執行之前就被呼叫，這時它依賴的欄位還沒初始化。
- 解法：在建構子裡只呼叫非 virtual 的成員；或建構完成後，由工廠呼叫 Initialize。
- 何時不算：無。
- 工具規則：CA2214、S1699。
- 範例：
```csharp
// 壞
abstract class Unit { protected Unit() { Init(); } protected abstract void Init(); }
// 好
abstract class Unit { public static T Create<T>() where T : Unit, new() { var u = new T(); u.Init(); return u; } protected abstract void Init(); }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2214

### F13 Member Could Be Static（不需要實例卻不是 static）
- 定義：成員完全沒用到實例資料，卻沒宣告成 static。
- 辨識訊號：方法本體沒碰任何實例欄位、屬性，也沒用 this。
- 為何有害：讀者會誤以為它依賴物件狀態；呼叫時還得先有一個實例。CA1822 被歸在效能類規則。
- 解法：加上 `static`。
- 何時不算：Unity 訊息方法（Update 等），由 Unity 執行期以實例呼叫（USP0014 會抑制這種情況的 CA1822）；為了實作介面或之後要 override 的成員。
- 工具規則：CA1822（.NET 10 預設 suggestion）、S2325。
- 範例：
```csharp
// 壞
int Clamp01(int v) => Math.Clamp(v, 0, 1);
// 好
static int Clamp01(int v) => Math.Clamp(v, 0, 1);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1822 ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/index.md

### F14 Ignored Return Value（忽略回傳值）
- 定義：呼叫沒有副作用、會回傳新值的方法，卻把結果丟掉；或忽略 Try 方法的成功旗標。
- 辨識訊號：`name.Trim();`、`s.Replace(a, b);` 單獨成一行；`int.TryParse(s, out var n);` 沒有判斷回傳值。
- 為何有害：字串是不可變的，結果不接起來等於什麼都沒做；忽略 TryParse 的結果，等於拿預設值往下跑。
- 解法：把結果指派回去；判斷 Try 方法的回傳值。
- 何時不算：刻意呼叫有副作用的方法，回傳值確實沒用（例如 `HashSet.Add` 只是要加入）。
- 工具規則：CA1806（.NET 10 預設 suggestion）、S2201。
- 範例：
```csharp
// 壞
name.Trim();   int.TryParse(s, out var n);
// 好
name = name.Trim();   if (!int.TryParse(s, out var n)) return;
```
- 來源：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca1806 ；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S2201.html

---

## G. 執行緒與同步

### G01 Locking on Public or Weak-Identity Objects（鎖在公開或身分不穩的物件上：lock(this)、lock(typeof)、lock(string)）
- 定義：用 `this`、`typeof(X)`、字串（包括字串常值）或其他外部也拿得到的物件當鎖。
- 辨識訊號：grep `lock \(this\)`、`lock \(typeof`、`lock \("`。
- 為何有害：外部程式碼也可能鎖同一個物件，造成死結或不必要的鎖競爭。Type 物件在整個應用程式裡只有一個；字串可能被 intern，不相干的程式碼會共用同一把鎖。
- 解法：用專用的 `private readonly object _gate = new();`；.NET 9 + C# 13 起用 `System.Threading.Lock`。不同的共享資源不要共用同一把鎖。
- 何時不算：型別本身是 private 或 internal，而且實例沒有公開的參考（CA2002 允許這種情況抑制 lock(this)）。
- 工具規則：CA2002（.NET 10 預設未啟用；涵蓋 string、值型別陣列、MarshalByRefObject、MemberInfo、ParameterInfo、Thread、this 等）、S2551（this、Type、string）、S3998、RCS1059。
- 範例：
```csharp
// 壞
lock (this) { _hp -= dmg; }
// 好
private readonly object _gate = new();   lock (_gate) { _hp -= dmg; }
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/statements/lock （Guidelines）；https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices ；https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/ca2002

### G02 Hand-Rolled Double-Checked Locking（自己寫雙重檢查鎖定）
- 定義：自己寫 `if (x == null) lock (...) if (x == null) x = new ...;` 來做延遲初始化。
- 辨識訊號：同一個欄位在 lock 外、lock 內各被檢查一次 null。
- 為何有害：Jon Skeet 指出，依 ECMA CLI 規格，沒有明確的記憶體屏障就不保證正確；寫法稍微不同就會壞；效能也不比其他寫法好。
- 解法：用 `Lazy<T>`（預設就是執行緒安全的），或直接用 static readonly 欄位初始化。需要非同步初始化時，快取一個 Task（AsyncLazy 模式）。
- 何時不算：無。
- 工具規則：沒查到 C# 專用規則。
- 範例：
```csharp
// 壞
if (_inst == null) lock (_g) if (_inst == null) _inst = new Registry();
// 好
static readonly Lazy<Registry> s_inst = new(() => new Registry());
```
- 來源：https://csharpindepth.com/articles/singleton ；https://learn.microsoft.com/en-us/dotnet/framework/performance/lazy-initialization

### G03 Unsynchronized Shared Collection（多執行緒共寫非執行緒安全的集合）
- 定義：多條執行緒同時寫入（或一條寫、多條讀）Dictionary、List、HashSet 這類非執行緒安全的集合，卻沒有任何同步。
- 辨識訊號：static 或 singleton 裡的 Dictionary，在 Task.Run、執行緒池或網路回呼中被 Add、Remove。
- 為何有害：System.Collections.Generic 的集合不提供任何同步。同時修改可能弄壞內部結構，後果無法預期（具體症狀未查證）。即使只有讀取，邊讀邊列舉也不是執行緒安全的。
- 解法：改用 `System.Collections.Concurrent` 的集合；或用 lock 保護所有存取；或讓集合只屬於單一執行緒（actor 或佇列）。
- 何時不算：建好之後只讀、不再修改；Dictionary 文件明說沒有修改時可以多個讀者並行。或使用 ImmutableDictionary、FrozenDictionary。
- 工具規則：沒查到靜態規則。
- 範例：
```csharp
// 壞
static readonly Dictionary<long, Session> s_sessions = new();   // 多個 I/O 回呼同時 Add/Remove
// 好
static readonly ConcurrentDictionary<long, Session> s_sessions = new();
```
- 來源：https://learn.microsoft.com/en-us/dotnet/api/system.collections.generic.dictionary-2 （Thread Safety）；https://learn.microsoft.com/en-us/dotnet/standard/collections/thread-safe/

### G04 Assuming GetOrAdd Factory Runs Once（以為 ConcurrentDictionary.GetOrAdd 的工廠只會跑一次）
- 定義：以為 `ConcurrentDictionary.GetOrAdd(key, factory)` 的工廠只會執行一次，就在工廠裡做昂貴或有副作用的事（建連線、扣資源），甚至在工廠裡 `.Result` 等非同步。
- 辨識訊號：GetOrAdd 的工廠 lambda 裡有 I/O、`new` 出昂貴資源，或 `.Result`。
- 為何有害：工廠是在鎖外面執行的，並行時可能被呼叫好幾次，最後只有一個結果會被存進去。在工廠裡同步等待，就是 sync-over-async（A03）。
- 解法：存 `Lazy<T>` 或 `Task<T>`，例如 `GetOrAdd(k, k => new Lazy<T>(...)).Value`；工廠本身保持便宜、沒有副作用。
- 何時不算：工廠便宜、沒有副作用，多跑幾次也無所謂。
- 工具規則：沒查到。
- 範例：
```csharp
// 壞
var conn = _pool.GetOrAdd(host, h => Connect(h));
// 好
var conn = _pool.GetOrAdd(host, h => new Lazy<Conn>(() => Connect(h))).Value;
```
- 來源：https://learn.microsoft.com/en-us/dotnet/api/system.collections.concurrent.concurrentdictionary-2.getoradd ；https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md （ConcurrentDictionary.GetOrAdd）

### G05 Thread.Sleep for Waiting or Polling（用 Thread.Sleep 等待或輪詢）
- 定義：用 Thread.Sleep 等某個條件成立（輪詢），或在 async 方法裡延遲。
- 辨識訊號：`while (!cond) Thread.Sleep(...)`；async 方法裡有 `Thread.Sleep`（見 A04）。
- 為何有害：async 方法裡的情況見 A04。同步程式裡用 Sleep 輪詢，一直占著執行緒，條件成立時反應也會延遲。
- 解法：async 裡用 `await Task.Delay`；等待事件用 SemaphoreSlim、ManualResetEventSlim 或 TaskCompletionSource；週期工作用 PeriodicTimer。
- 何時不算：專用背景執行緒上刻意節流的簡單迴圈（推論）。
- 工具規則：S4462（async 方法內）、S2925（測試裡）。
- 範例：
```csharp
// 壞
while (!_ready) Thread.Sleep(10);
// 好
await _readyTcs.Task;   // 由「就緒」那一方呼叫 SetResult
```
- 來源：https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming （Figure 5）；https://github.com/SonarSource/sonar-dotnet/blob/master/analyzers/rspec/cs/S4462.html

### G06 Timer Leak or Reentrancy（Timer 沒停、沒保留參考，或回呼會重入）
- 定義：建立 `System.Threading.Timer` 後沒保留參考、也沒 Dispose；或回呼的執行時間可能比週期長，卻沒有防止重入。
- 辨識訊號：`new Timer(...)` 的結果沒有存到欄位；類別的 Dispose 裡沒有 `_timer.Dispose()`；回呼裡沒有防重入旗標。
- 為何有害：官方文件：使用 Timer 期間必須保留它的參考，否則它會像其他受控物件一樣被 GC 回收而停止。沒 Dispose 會一直觸發，回呼捕捉的物件也一直活著。回呼在 thread pool 上執行，週期比執行時間短時，會在兩條執行緒上同時執行。Dispose 之後，仍可能有已經排定的回呼在執行。
- 解法：存成欄位，在 Dispose 裡釋放；回呼要能重入，或用 Interlocked 旗標防止重入；async 的週期工作改用 PeriodicTimer。
- 何時不算：無。
- 工具規則：沒有 Timer 專用規則；適用一般的 IDisposable 規則（CA2000、CA1001、CA2213）。
- 範例：
```csharp
// 壞
new Timer(_ => Flush(), null, 0, 1000);   // 沒保存、沒 Dispose，回呼可能重疊
// 好
using var t = new PeriodicTimer(TimeSpan.FromSeconds(1)); while (await t.WaitForNextTickAsync(ct)) await FlushAsync(ct);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/api/system.threading.timer （Remarks）；https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md （Timer callbacks）

### G07 Coarse or Hot-Path Locking（熱路徑上鎖、鎖的範圍太大）
- 定義：在熱路徑上取鎖；在鎖裡做 I/O 或長時間計算；用一把全域鎖保護互不相關的資源；簡單的計數也用 lock。
- 辨識訊號：lock 區塊裡有 await 以外的 I/O 呼叫或大迴圈；整個類別只有一個 `_lock`，卻保護多種狀態；`lock (_g) { _count++; }`。
- 為何有害：鎖競爭變多、吞吐量下降、死結的機會增加。ASP.NET Core 指引明講：不要在常用的程式路徑上取鎖。
- 解法：縮短持鎖時間；不同資源用不同的鎖；簡單的原子操作用 Interlocked；可以的話就避免共享（狀態改成每執行緒或每連線一份）。
- 何時不算：低頻路徑上的短臨界區。
- 工具規則：沒查到。
- 範例：
```csharp
// 壞
lock (_gate) { _count++; }
// 好
Interlocked.Increment(ref _count);
```
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/statements/lock （Hold a lock for as short time as possible）；https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices （Interlocked）；https://learn.microsoft.com/en-us/aspnet/core/fundamentals/best-practices （Do not acquire locks in common code paths）

---

## H. Unity C# 特有

### H01 Per-Frame Lookups（每幀做 GetComponent／Find 查找）
- 定義：在 Update、FixedUpdate、LateUpdate 裡呼叫 `GetComponent`、`GameObject.Find`、`FindObjectOfType`、`FindWithTag` 來取得引用。
- 辨識訊號：grep Unity 每幀方法內的 `GetComponent<`、`Find(`、`FindObjectOfType`、`FindWithTag`；`GetComponent` 之後緊接著判斷 null。
- 為何有害：每幀重複搜尋。官方文件：`GameObject.Find` 在規模變大時會明顯拖慢效能，不建議用在效能關鍵的程式，特別是 Update。`GetComponent` 搭配 null 檢查時，如果元件不存在，會產生配置（UNT0026）。
- 解法：在 Awake 或 Start 裡快取到欄位；用 `[SerializeField]` 在 Inspector 裡指派；用 `[RequireComponent]` 保證元件存在；元件可能不存在時用 `TryGetComponent`。
- 何時不算：一次性的初始化，或由事件觸發、不是每幀都跑的低頻呼叫。
- 工具規則：UNT0026（GetComponent 後判 null，建議改 TryGetComponent）、UNT0039（對自己 GetComponent 時應加 RequireComponent）、UNT0003（非泛型的 GetComponent）；Find 系列可以用 RS0030 自訂禁用。
- 範例：
```csharp
// 壞
void Update() { GetComponent<Rigidbody>().AddForce(force); }
// 好
Rigidbody _rb; void Awake() => _rb = GetComponent<Rigidbody>();   void Update() => _rb.AddForce(force);
```
- 來源：https://docs.unity3d.com/ScriptReference/GameObject.Find.html ；https://unity.com/how-to/best-practices-performance-optimization-unity ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/UNT0026.md

### H02 Camera.main in Update（每幀存取 Camera.main）
- 定義：每幀甚至一幀內多次存取 `Camera.main`。
- 辨識訊號：Update 裡出現 `Camera.main.`。
- 為何有害：新版 Unity 內部會快取帶 MainCamera tag 的物件，但每次存取仍有一點 CPU 開銷，官方說「和 GetComponent 差不多」。官方最佳實務頁也說，Camera.main 以前非常昂貴，現在已經不是了。舊版的具體版本號未查證。
- 解法：快取到欄位；如果會切換相機，就在切換事件裡更新。
- 何時不算：低頻呼叫。
- 工具規則：沒查到 UNT 規則。
- 範例：
```csharp
// 壞
void Update() { var ray = Camera.main.ScreenPointToRay(Input.mousePosition); }
// 好
Camera _cam; void Start() => _cam = Camera.main;   void Update() { var ray = _cam.ScreenPointToRay(Input.mousePosition); }
```
- 來源：https://docs.unity3d.com/ScriptReference/Camera-main.html ；https://unity.com/how-to/best-practices-performance-optimization-unity

### H03 Tag String Comparison（用 == 比較 tag 字串）
- 定義：用 `gameObject.tag == "Enemy"` 比較 tag。
- 辨識訊號：grep `\.tag ==`、`tag.Equals(`。
- 為何有害：UNT0002：用 == 比較 tag 比內建的 CompareTag 慢。拼錯的 tag 也是魔術字串（F11）。
- 解法：`CompareTag("Enemy")`。新版 Unity 有 `CompareTag(TagHandle)` 多載，重複使用同一個 TagHandle 時更快。
- 何時不算：無。
- 工具規則：UNT0002。
- 範例：
```csharp
// 壞
if (other.tag == "Enemy") Hit(other);
// 好
if (other.CompareTag("Enemy")) Hit(other);
```
- 來源：https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/UNT0002.md ；https://docs.unity3d.com/ScriptReference/GameObject.CompareTag.html

### H04 Empty Unity Messages（空的 Update 等 Unity 訊息方法）
- 定義：留著空的 `Update()`、`FixedUpdate()`、`Start()` 等 Unity 訊息方法；或 Update 裡只是在等某個少見的條件成立。
- 辨識訊號：方法本體是空的 Unity 訊息方法；Update 裡只有 `if (rareFlag) {...}`。
- 為何有害：就算方法是空的，Unity 執行期還是會呼叫它。官方最佳實務頁也指出，「條件成立才做事」的 Update 寫法，會產生大量實際上什麼都沒做的每幀回呼。
- 解法：刪掉空方法；低頻邏輯改成事件驅動，或在不需要時 `enabled = false`。
- 何時不算：無。
- 工具規則：UNT0001。
- 範例：
```csharp
// 壞
void Update() { }
// 好
// 直接刪除；需要時才加回來
```
- 來源：https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/UNT0001.md ；https://unity.com/how-to/best-practices-performance-optimization-unity

### H05 Per-Frame GC Allocation（每幀產生 GC 配置）
- 定義：每幀執行的程式碼在堆積上配置：new 參考型別、字串串接或格式化、閉包、LINQ、裝箱、params、會回傳陣列的 Unity API、Debug.Log。
- 辨識訊號：Update 系列方法裡有 `new `（參考型別）、字串 `+`、lambda、LINQ、`Debug.Log`；UI 文字每幀重新指派。
- 為何有害：Unity 的 GC 不是世代式的，頻繁的小配置會累積成 GC 尖峰，畫面就卡一下。官方最佳實務也提醒，Update 裡的 log 會拖慢效能。
- 解法：預先配置並重用（`List.Clear()`）；用物件池；用 StringBuilder；UI 文字只在值變動時更新；建置版本裡關掉 Debug.Log；用 Profiler 找出配置來源。
- 何時不算：場景載入、初始化這類非每幀的路徑。
- 工具規則：這是綜合性的壞味道，沒有單一規則。相關規則：UNT0044（TextMeshPro 設定文字時的暫時字串）、UNT0028（非配置的物理 API）、UNT0038、RCS1198、S1643。
- 範例：
```csharp
// 壞
void Update() { scoreText.text = "Score: " + score; }
// 好
void SetScore(int v) { if (v == _shown) return; _shown = v; scoreText.text = "Score: " + v.ToString(); }
```
- 來源：https://docs.unity3d.com/Manual/performance-reference-types.html ；https://unity.com/how-to/best-practices-performance-optimization-unity ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/index.md

### H06 Repeated Array-Returning API Access（迴圈裡重複存取會回傳陣列的 Unity API）
- 定義：在迴圈裡反覆存取每次都會回傳新陣列的 Unity API，例如 `mesh.vertices`、`Input.touches`、`Physics.RaycastAll`、`renderer.sharedMaterials`、`animator.parameters`。
- 辨識訊號：for 迴圈的條件或本體裡出現 `mesh.vertices[`、`mesh.vertices.Length`。
- 為何有害：Unity 文件：所有回傳陣列的 Unity API，每次存取都會建立一份新複本。放在迴圈裡就是 N 次配置加複製。
- 解法：在迴圈外取一次；改用不配置的版本（`RaycastNonAlloc`、`GetVertices(List)`、`touchCount` 搭配 `GetTouch(i)`、`GetSharedMaterials`）。
- 何時不算：迴圈外只取一次。
- 工具規則：UNT0042（在迴圈裡存取 Mesh 的陣列屬性）、UNT0028（非配置的物理 API）、UNT0045（非配置的陣列存取）。
- 範例：
```csharp
// 壞
for (int i = 0; i < mesh.vertices.Length; i++) Use(mesh.vertices[i]);
// 好
var verts = mesh.vertices; for (int i = 0; i < verts.Length; i++) Use(verts[i]);
```
- 來源：https://docs.unity3d.com/Manual/performance-optimizing-arrays.html ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/index.md

### H07 foreach Allocation on Old Unity or via Interface（舊版 Unity 的 foreach，或透過介面 foreach 產生配置）
- 定義：在 Unity 5.5 之前的編譯器上，對 `List<T>` foreach 會配置；而在任何版本，透過介面型別（`IEnumerable<T>` 等）foreach 都會把 struct 列舉器裝箱。
- 辨識訊號：熱路徑方法的參數或欄位宣告成 `IEnumerable<T>`，然後用 foreach 走訪；專案還在用很舊的 Unity。
- 為何有害：struct 列舉器被當成介面使用時會裝箱。Jackson Dunstan 實測：Unity 5.5 以後對具體型別 `List<T>` foreach 不再產生垃圾，但透過 `IEnumerable<T>` foreach 每次迴圈約 40 bytes 垃圾。這是第三方實測，不是 Unity 官方資料。
- 解法：熱路徑上，參數和欄位宣告成具體型別（`List<T>`、陣列）再 foreach，或用 `IReadOnlyList<T>` 搭配 for 索引。
- 何時不算：Unity 5.5 以後對具體集合型別 foreach；陣列一直都不會配置。
- 工具規則：沒查到。
- 範例：
```csharp
// 壞（熱路徑）
void Tick(IEnumerable<Unit> units) { foreach (var u in units) u.Step(); }
// 好
void Tick(List<Unit> units) { foreach (var u in units) u.Step(); }
```
- 來源：https://jacksondunstan.com/articles/3805 （第三方實測）

### H08 Coroutine Leak & Yield Allocation（協程洩漏與 yield 配置）
- 定義：協程沒有結束條件，也沒有停止機制；以為把腳本 `enabled = false` 就會停止協程；每一輪都 `yield return new WaitForSeconds(x)`；頻繁啟動新協程；呼叫回傳 IEnumerator 的方法時忘了包 StartCoroutine。
- 辨識訊號：協程裡有 `while (true)`，沒有中止條件，Coroutine 參考也沒保存；`yield return new WaitForSeconds`；直接呼叫 `Fade();`（回傳 IEnumerator）而沒有 StartCoroutine。
- 為何有害：Unity 文件：協程只在呼叫 StopCoroutine／StopAllCoroutines、宿主 GameObject 被停用、或 MonoBehaviour 被 Destroy 時才會停；**把腳本 `enabled` 設成 false 不會停止協程**。協程一直活著，它引用的物件也一直活著，形成洩漏。每次 `new WaitForSeconds` 都會配置。每個協程都有啟動開銷，官方建議用長壽的協程搭配 `yield return null`，不要頻繁啟動新的。沒包 StartCoroutine 的呼叫，協程根本不會執行（UNT0012）。
- 解法：協程要有明確的結束條件；保存 Coroutine 參考，在 OnDisable 或 OnDestroy 停掉；快取 WaitForSeconds（UNT0038 建議放 static 欄位）；用長壽協程取代頻繁啟動。Unity 的 Awaitable 是池化的，配置通常比 iterator 協程少，可以考慮。
- 何時不算：有明確終點的短協程。
- 工具規則：UNT0038（快取 WaitForSeconds）、UNT0012（協程回傳值沒被使用）。
- 範例：
```csharp
// 壞
IEnumerator Regen() { while (true) { hp++; yield return new WaitForSeconds(1f); } }
// 好
static readonly WaitForSeconds s_1s = new(1f);
IEnumerator Regen() { while (hp < maxHp) { hp++; yield return s_1s; } }
```
- 來源：https://docs.unity3d.com/Manual/Coroutines.html ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/UNT0038.md ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/UNT0012.md ；https://docs.unity3d.com/Manual/async-awaitable-introduction.html

### H09 C# Null Operators on UnityEngine.Object（對 Unity 物件用 ?.、??、is null）
- 定義：對 UnityEngine.Object（GameObject、Component、ScriptableObject 等）用 `?.`、`??`、`??=`、`is null` 或 `is not null` 判斷物件是否還活著。
- 辨識訊號：Unity 物件型別的變數後面接 `?.`，或用在 `??`、`??=`、`is null` 上。
- 為何有害：Unity 覆寫了 `==`。底層的 C++ 物件被 Destroy 之後，C# 包裝物件仍然存在，但 `== null` 會回傳 true；編輯器裡還有所謂的 fake null。`?.`、`??` 和模式比對做的是純 C# 的 null 檢查，會繞過 Unity 的語意，於是對已銷毀的物件繼續呼叫，拋出例外。另外，Unity 自訂的 `==` 比較慢，也不是執行緒安全的，不能在主執行緒以外比較。
- 解法：明確寫 `if (obj != null)`。
- 何時不算：一般的 C# 物件（不是 UnityEngine.Object）。
- 工具規則：UNT0007（??）、UNT0008（?.）、UNT0023（??=）、UNT0029（模式比對 null）。USP0001、USP0002 會抑制 IDE 對 Unity 物件提出的這類誤導建議。
- 範例：
```csharp
// 壞
target?.TakeDamage(10);
// 好
if (target != null) target.TakeDamage(10);
```
- 來源：https://unity.com/blog/engine-platform/custom-operator-should-we-keep-it ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/UNT0008.md

### H10 String-Based Animator/Shader Property Access（用字串名稱存取 Animator／Shader 屬性）
- 定義：每次都用字串名稱呼叫 `animator.SetFloat("Speed", v)`、`material.SetColor("_Color", c)`。
- 辨識訊號：熱路徑上的 `SetFloat("`、`SetBool("`、`SetTrigger("`、`SetColor("`、`SetFloat("_`。
- 為何有害：每次呼叫都要把字串換成內部 ID。官方建議用 `Animator.StringToHash`、`Shader.PropertyToID` 取得 ID，然後快取起來。
- 解法：用 `static readonly int` 快取 hash 或 ID。
- 何時不算：一次性的設定。
- 工具規則：UNT0041（重複呼叫 Animator 方法時用 StringToHash）、UNT0046（快取 Shader.PropertyToID）。
- 範例：
```csharp
// 壞
animator.SetFloat("Speed", v);
// 好
static readonly int SpeedId = Animator.StringToHash("Speed");   animator.SetFloat(SpeedId, v);
```
- 來源：https://unity.com/how-to/best-practices-performance-optimization-unity ；https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/index.md

### H11 Instantiate/Destroy Churn（頻繁 Instantiate／Destroy，不用物件池）
- 定義：頻繁 Instantiate 與 Destroy 短命的物件，例如子彈、特效、傷害數字。
- 辨識訊號：射擊、命中、生成怪物等高頻事件裡出現 `Instantiate(` 和 `Destroy(`。
- 為何有害：官方最佳實務：Instantiate 和 Destroy 會產生垃圾，造成 GC 尖峰。
- 解法：用物件池（`UnityEngine.Pool` 或自製）。不用時停用物件，而不是銷毀。
- 何時不算：低頻、一次性的生成。
- 工具規則：沒查到。
- 範例：
```csharp
// 壞
var b = Instantiate(bulletPrefab, pos, rot); Destroy(b, 2f);
// 好
var b = _pool.Get(); b.transform.SetPositionAndRotation(pos, rot);   /* 用完 */ _pool.Release(b);
```
- 來源：https://unity.com/how-to/best-practices-performance-optimization-unity ；https://docs.unity3d.com/Manual/performance-optimizing-code-managed-memory.html （Pooling and reusing objects 子頁）

### H12 God MonoBehaviour（巨型 MonoBehaviour）
- 定義：一個 MonoBehaviour 同時負責輸入、移動、戰鬥、UI、網路、存檔等多種職責，長達數千行，Update 裡塞滿 if 分支。
- 辨識訊號：單一檔案數千行；Update 裡有好幾段互不相關的邏輯；大量 `[SerializeField]` 欄位分屬不同子系統；常用 partial 或 region 掩飾（F01、F02）。
- 為何有害：跟一般的 Large Class 一樣：難懂、難測試，改一處牽動全身。在 Unity 裡還會讓 prefab 失去組合彈性（推論）。
- 解法：依職責拆成多個元件，用組合代替；純邏輯抽成一般的 C# 類別，就能寫單元測試；資料抽成 ScriptableObject（Unity 官方的架構建議這次未查證）。
- 何時不算：原型或 game jam 等用完即丟的程式碼。
- 工具規則：通用的複雜度與耦合指標：CA1502、CA1506、S1200、S138、S3776。
- 範例：
```csharp
// 壞
public class Player : MonoBehaviour { void Update() { HandleInput(); Move(); Fight(); DrawHud(); SyncNet(); AutoSave(); } }
// 好
[RequireComponent(typeof(PlayerMotor), typeof(PlayerCombat))] public sealed class PlayerInput : MonoBehaviour { /* 只處理輸入 */ }
```
- 來源：https://refactoring.guru/smells/large-class （Unity 專屬的官方指引未查證）

---

## 2. 依工具規則反查條目（看到 analyzer 警告時用）

| 規則 | 條目 |
|---|---|
| CS4014 | A07 |
| CS1996 | A15 |
| CA1001 / CA2213 / CA2215 | B02 |
| CA1002 / CA1819 / CA2227 | D08 |
| CA1021 / CA1045 | F08 |
| CA1031 | C01 |
| CA1051 | F06 |
| CA1062 | F10 |
| CA1063 / CA1816 | B03 |
| CA1065 / CA2219 | C06 |
| CA1068 / CA2016 / CA2250 | A08 |
| CA1501 | F07 |
| CA1502 / CA1506 | F01, H12 |
| CA1507 | F11 |
| CA1806 | F14 |
| CA1815 | E03 |
| CA1821 | B04 |
| CA1822 | F13 |
| CA1825 / CA1861 | E06 |
| CA1827 / CA1829 / CA1836 / CA1860 | D02 |
| CA1841 / CA1853 / CA1854 / CA1864 | D06 |
| CA1849 | A03, A04 |
| CA1851 | D01 |
| CA1862 / CA1307 / CA1309 / CA1310 | E09 |
| CA2000 | B01（也適用 G06） |
| CA2002 | G01 |
| CA2007 | A09 |
| CA2012 | A10 |
| CA2025 | A07, B01 |
| CA2200 | C03 |
| CA2201 | C07 |
| CA2211 | F04 |
| CA2214 | F12 |
| CA2247 | A14 |
| IDE0250 | E03 |
| S107 / S3874 | F08 |
| S108 / S2486 / S6667 | C02 |
| S110 | F07 |
| S1104 / S2357 | F06 |
| S1155 | D02 |
| S1163 / S3877 | C06 |
| S1168 / S3900 | F10 |
| S1192 / S2302 / S109 | F11 |
| S1215 | B09 |
| S1643 | E02 |
| S1696 | C07 |
| S1699 | F12 |
| S2201 | F14 |
| S2221 | C01 |
| S2223 / S2386 / S2696 / S3010 | F04 |
| S2325 | F13 |
| S2365 / S3956 / S4004 | D08 |
| S2551 / S3998 | G01 |
| S2737 | C04 |
| S2925 | G05 |
| S2930 | B01 |
| S2931 / S2952 | B02 |
| S2953 / S3234 / S3881 / S3966 | B03 |
| S2971 | D04 |
| S3011 | E07 |
| S3168 | A01 |
| S3172 | B05 |
| S3216 | A09 |
| S3445 | C03 |
| S4225 / S4226 | F03 |
| S4457 | A16 |
| S4462 | A03, A04, A13, G05 |
| S4586 | A12 |
| S5034 | A10 |
| S6602 / S6603 / S6605 / S6608 / S6617 | D03 |
| S6962 | B06 |
| S6966 | A04 |
| S7133 | A15 |
| RCS1044 | C03 |
| RCS1059 | G01 |
| RCS1075 | C02 |
| RCS1077 | D03 |
| RCS1080 | D02 |
| RCS1090 | A09 |
| RCS1155 | E09 |
| RCS1198 | E01 |
| RCS1210 | A12 |
| RCS1229 | A11 |
| RCS1242 | E03 |
| RCS1265 | C04 |
| VSTHRD002 | A03, A13 |
| VSTHRD100 | A01 |
| VSTHRD101 | A02 |
| VSTHRD103 | A04 |
| VSTHRD110 | A07 |
| VSTHRD111 | A09 |
| VSTHRD114 | A12 |
| SA1123 / SA1124 | F02 |
| UNT0001 | H04 |
| UNT0002 | H03 |
| UNT0003 / UNT0026 / UNT0039 | H01 |
| UNT0007 / UNT0008 / UNT0023 / UNT0029 | H09 |
| UNT0012 / UNT0038 | H08 |
| UNT0018 | E07 |
| UNT0028 / UNT0042 / UNT0045 | H06 |
| UNT0041 / UNT0046 | H10 |
| UNT0044 | H05 |

---

## 3. 主要來源清單

- David Fowler, AsyncGuidance：https://github.com/davidfowl/AspNetCoreDiagnosticScenarios/blob/master/AsyncGuidance.md
- Stephen Cleary, Async/Await Best Practices（MSDN 2013）：https://learn.microsoft.com/en-us/archive/msdn-magazine/2013/march/async-await-best-practices-in-asynchronous-programming
- Stephen Toub, ConfigureAwait FAQ：https://devblogs.microsoft.com/dotnet/configureawait-faq/
- Stephen Toub, async-over-sync／sync-over-async：https://devblogs.microsoft.com/dotnet/should-i-expose-asynchronous-wrappers-for-synchronous-methods/ ；https://devblogs.microsoft.com/dotnet/should-i-expose-synchronous-wrappers-for-asynchronous-methods/
- ASP.NET Core Best Practices：https://learn.microsoft.com/en-us/aspnet/core/fundamentals/best-practices
- .NET code quality rules 索引：https://learn.microsoft.com/en-us/dotnet/fundamentals/code-analysis/quality-rules/
- Best practices for exceptions：https://learn.microsoft.com/en-us/dotnet/standard/exceptions/best-practices-for-exceptions
- Implement a Dispose method／Dispose pattern：https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/implementing-dispose ；https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/dispose-pattern
- HttpClient guidelines：https://learn.microsoft.com/en-us/dotnet/fundamentals/networking/http/httpclient-guidelines
- DI guidelines：https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines
- Framework Design Guidelines（struct、field、parameter、extension、exception）：https://learn.microsoft.com/en-us/dotnet/standard/design-guidelines/
- Managed threading best practices：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices
- lock statement：https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/statements/lock
- SonarAnalyzer C# rspec：https://github.com/SonarSource/sonar-dotnet/tree/master/analyzers/rspec/cs
- Roslynator：https://josefpihrt.github.io/docs/roslynator/analyzers/ （規則清單：https://github.com/dotnet/roslynator/blob/main/src/Analyzers.xml）
- VS Threading Analyzers：https://microsoft.github.io/vs-threading/analyzers/
- Microsoft.Unity.Analyzers：https://github.com/microsoft/Microsoft.Unity.Analyzers/blob/main/doc/index.md
- Unity Manual（managed memory、arrays、reflection、coroutines、awaitable）：https://docs.unity3d.com/Manual/performance-reference-types.html ；https://docs.unity3d.com/Manual/performance-optimizing-arrays.html ；https://docs.unity3d.com/Manual/performance-gc-avoid-reflection.html ；https://docs.unity3d.com/Manual/Coroutines.html ；https://docs.unity3d.com/Manual/async-awaitable-continuations.html
- Unity 效能最佳實務：https://unity.com/how-to/best-practices-performance-optimization-unity
- Unity custom == 部落格：https://unity.com/blog/engine-platform/custom-operator-should-we-keep-it

---

## 4. 未查證／推論項目一覽（使用時注意）

- A03：Unity 主執行緒上 `.Result` 會死結。Unity 文件只確認了 UnitySynchronizationContext 會讓續行回主執行緒，死結是依 Cleary 的機制推論。
- A05：背景執行緒能不能呼叫 Unity API，未查證。
- A06：async 迴圈在 await 期間會歸還執行緒，屬推論。
- A09：Unity 遊戲碼不要加 ConfigureAwait(false)，依 Toub 的「應用層不要用」原則推論。
- A15：Monitor 跨 await 無法正確釋放，是依擁有權語意推論，未逐字查證。
- C01：「最後防線可以 catch Exception」是實務判斷；CA1031 官方寫的是不要抑制。
- D03：「熱路徑避免 LINQ」是由閉包、委派、列舉器配置等機制得出的推論，沒有單一官方條文。
- E01：新版 Roslyn 是否已自動消除 `string + int` 的裝箱，以及 Unity 是否支援 interpolated string handler，都未查證。
- E08：dynamic 在 IL2CPP／AOT 上的相容性，未查證。
- F01：「用 partial 切巨型類別是壞味道」是推論；官方只列出 partial 的正當用途，沒有明文禁止。
- F08：S107 的預設參數數量門檻，未查證。
- G03：多執行緒同時寫 Dictionary 的具體損毀症狀，未查證。
- H02：Camera.main 從哪個版本開始改成快取，未查證具體版本號。
- H07：foreach 的配置數據來自第三方實測（Jackson Dunstan），不是 Unity 官方資料。
- H12：Unity 官方的架構建議（例如 ScriptableObject），這次未查證。
- RS0030 的規則編號來自第三方 SSW 規則頁；BannedApiAnalyzers 本身的說明文件已查證。

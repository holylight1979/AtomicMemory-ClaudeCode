# 05 並行／效能／資源 壞味道（語言中立）

> 閱讀樹：[README.md](README.md)（分類樹、症狀路由、重疊對照）｜全條目一句話索引：[00-index.md](00-index.md)

> **用途**：查「這段程式碼在並行、效能、記憶體與資源、狀態一致性、可觀測性方面有沒有壞味道」。
> **壞味道（code smell）**：不一定是 bug，但常是 bug 或效能問題的前兆，值得停下來看一眼。
> **範圍**：語言中立的通用原理，例子多用 C#。C# 語言特有細節（async/await 陷阱、IDisposable 實作細節）與 client/server 協定見 [03-csharp-dotnet.md](03-csharp-dotnet.md)、[04-client-server.md](04-client-server.md)。
> **來源標記**：沒標記＝讀過原文頁面或原文 PDF；〔摘要〕＝只經搜尋結果摘要確認，沒逐字讀原文；〔未查證〕＝找不到可靠來源，屬推論。

## 給查閱者（含 LLM）的使用規則

1. 先用下方「分類架構」定位，再拿條目的「辨識訊號」比對程式碼或量測數據。
2. 「何時不算」是防誤報用：命中訊號、但符合「何時不算」→ 不要報。
3. **並行正確性類**（A 類）看程式形狀就可以報，因為這類 bug 很難重現，等重現才報就太晚。
4. **效能類**（B 類）大多要有量測佐證才算數，沒數據時只能報「疑似」，並參考〔Premature Optimization〕條目。
5. 條目之間用〔英文名〕互相參照。

---

## 這個切面的分類架構

```
A. 並行（Concurrency）：多條執行緒同時碰同一份東西時出錯或互卡
   A1 共享狀態與原子性（atomicity，不可被插隊的完整性）：資料被多條執行緒同時讀寫，
      別人看到做一半的中間狀態
      - Unsynchronized Shared Mutable State / Non-atomic Read-Modify-Write / Check-Then-Act
      - Composing Independently Atomic Calls / Order Violation / Invariant Split Across Locks
      - Volatile as Synchronization / Broken Double-Checked Locking
      - Unsafe Publication / Mutable Static State in Server Code
   A2 鎖的設計：鎖太大、太碎、順序亂，或持鎖時做了不該做的事
      - Coarse-Grained Lock (One-Lane Bridge) / Over-Synchronization / Inconsistent Lock Ordering
      - Calling Alien Methods While Holding a Lock / Blocking While Holding a Lock
      - Locking on Publicly Accessible Objects / Lock Not Released on Exception
   A3 等待與通知：該睡的時候在空轉，或醒來後沒再確認條件
      - Busy Waiting / Condition Wait Without Loop
   A4 執行緒數量與生命週期：開太多、收不掉、互相等、硬殺
      - Thread-per-Request / More Is Less / Thread Leak
      - Interdependent Tasks in a Bounded Pool / Forcible Thread Termination / Stale ThreadLocal

B. 效能（Performance）：結果正確，但太慢或太耗資源
   B1 白做的工：不需要、重複、反覆轉換、多餘拷貝
      - Unnecessary Processing / Repeated Computation / Tower of Babel / Unnecessary Deep Copy
   B2 演算法與成長：資料一大就爆
      - Hidden Quadratic / The Ramp
   B3 I/O 往返：來回次數太多或每次搬太多
      - Circuitous Treasure Hunt (N+1) / Empty Semi Trucks (Chatty I/O) / Sisyphus Database Retrieval
   B4 配置與實例化：熱路徑（hot path，被極頻繁執行的程式碼）上不斷建立物件
      - Excessive Dynamic Allocation / Improper Instantiation
   B5 負載與排隊：工作分配不均、尖峰積壓、故障連鎖
      - Blob / Unbalanced Processing / Traffic Jam / Falling Dominoes (Retry Storm) / Are We There Yet?
   B6 最佳化判斷本身出錯
      - Premature Optimization / Over-Caching / Cache Without Invalidation

C. 記憶體與資源（Memory & Resource）
   C1 記憶體洩漏（GC 語言裡的洩漏＝不再需要的物件仍被參考，GC 收不走）
      - Event Subscription Leak / Ever-Growing Static Collection / Unbounded Cache / Closure Capture Leak
   C2 作業系統資源與配置策略
      - Resource Not Released / Object Pool Misuse / Temporary Large Objects (LOH)

D. 狀態一致性（State Consistency）：同一個事實存了不只一份
      - Duplicated State / Redundant or Contradictory State

E. 可觀測性（Observability，從外部看得出系統在做什麼、出了什麼事）
      - Swallowed Exception / Ignored Return Value / Silent Fallback
      - Silent Failure in Background Tasks / Excessive Logging / Insufficient Logging / No Metrics
```

附錄：A＝Smith & Williams 效能反模式速查；B＝Azure 效能反模式對照；C＝能源壞味道 12 類；D＝研究數據；E＝來源清單與查證狀態。

---

# A. 並行（Concurrency）

## A1 共享狀態與原子性

### Unsynchronized Shared Mutable State（未同步的共享可變狀態）
- 定義：兩條以上執行緒讀寫同一個可變變數，卻沒有任何同步保護。
- 辨識訊號：欄位（尤其 static 欄位或單例的成員）會在多個執行緒入口被寫入，例如 request handler、Timer 回呼、`Task.Run`、事件回呼，而讀寫處都不在 `lock`／`Interlocked`／並行集合保護下；同一輸入多跑幾次結果不同；錯誤只在壓力測試或正式環境出現。
- 為何有害：結果取決於哪條執行緒先跑到，每次執行結果都可能不同、無法預測（Microsoft）。Lu 等人分析 105 個真實並行 bug，97% 的非死結 bug 屬於「原子性違反」或「順序違反」這兩種簡單樣式。
- 解法：Java Concurrency in Practice（JCIP）的三選一：不共享（限制在單一執行緒）、改成不可變、每次存取都同步。
- 何時不算：變數只在一條執行緒內使用；物件建構後就不再改、且已安全交給其他執行緒（見〔Unsafe Publication〕）；刻意設計成容忍競爭的近似值（例如統計用計數器），且有註解說明。Microsoft 也提到演算法可以調整成容忍競爭，而不一定要消除競爭。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices ；https://www.cs.columbia.edu/~junfeng/08fa-e6998/sched/readings/concurrency-bugs.pdf ；JCIP 三選一引文：https://www.cs.tufts.edu/comp/150CCP/lectures/Lecture16.pdf 〔摘要〕

### Non-atomic Read-Modify-Write（非原子的讀-改-寫）
- 定義：`x++`、`x += n`、`flag ^= true` 看起來是一行，實際上是「讀出→修改→寫回」三步，中間可以被別的執行緒插隊。
- 辨識訊號：共享欄位上出現 `++`、`--`、`+=`、`|=` 等複合賦值，且不在鎖內、也沒用 `Interlocked`；高併發下計數總數比預期少。
- 為何有害：一條執行緒讀完、還沒寫回就被搶先，另一條執行緒寫入的值會被覆蓋，也就是更新遺失（lost update）。Microsoft 以 `objCt++` 為標準例子。
- 解法：`Interlocked.Increment`／`Add`／`CompareExchange`；或用 `lock`；Java 用 `AtomicInteger` 等原子類別。
- 何時不算：區域變數；只有一個寫入者，而且讀者可接受讀到稍舊的值。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices ；https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/visibility-and-atomicity-vna/vna02-j

### Check-Then-Act（先檢查再行動）
- 定義：先檢查一個條件，再依結果行動；但兩步之間，狀態可能已被別的執行緒改掉。
- 辨識訊號：`if (!dict.ContainsKey(k)) dict.Add(k, v)`；`if (File.Exists(p)) File.Open(p)`；`if (x == null) x = new X()`；`if (balance >= amt) balance -= amt`。併發下出現重複鍵例外、重複初始化、超賣。
- 為何有害：檢查時成立的前提，到行動時可能已不成立；就算每個呼叫各自是執行緒安全的也一樣。Microsoft 的提醒是：每寫一行，都要想「如果在這行之前被搶先，另一條執行緒跑過去會怎樣」。
- 解法：把檢查與行動放進同一把鎖；或改用一步到位的原子 API，例如 `ConcurrentDictionary.GetOrAdd`／`TryAdd`、`Interlocked.CompareExchange`、資料庫唯一鍵約束搭配衝突處理、檔案用「不存在才建立」的開檔模式直接開。
- 何時不算：單執行緒；檢查只是快速路徑的最佳化，後面的行動本身還會原子性地再確認一次（例如 `TryAdd` 失敗時有處理）。
- 來源：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/visibility-and-atomicity-vna/vna03-j ；https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices

### Composing Independently Atomic Calls（把多個各自原子的呼叫當成整體原子）
- 定義：以為每個方法各自是執行緒安全的，連續呼叫幾個也就安全。
- 辨識訊號：對同步集合或並行集合連續呼叫兩個以上方法（先 `Count` 再用索引、先 `Add` 再 `ToArray`）；兩個 `AtomicReference`／`Interlocked` 欄位在邏輯上必須一起更新。
- 為何有害：別的執行緒可以插在兩次呼叫之間。CERT 的例子：兩個原子參考分別更新，另一條執行緒可能把新的 first 和舊的 second 湊在一起用。
- 解法：用單一鎖包住整組操作；改用提供複合操作的 API；或把相關欄位封裝成一個不可變物件，一次替換整個參考（`CompareExchange`）。
- 何時不算：幾個呼叫之間不存在「必須一致」的關係。
- 來源：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/visibility-and-atomicity-vna/vna03-j

### Order Violation（順序違反：假設的執行順序沒有被保證）
- 定義：程式默默假設「A 一定比 B 先發生」，例如先初始化再使用、先設好欄位再觸發回呼，但沒有任何同步機制保證這個順序。
- 辨識訊號：建構子或 `Init()` 裡先啟動執行緒、計時器或訂閱事件，之後才設定那條執行緒會用到的欄位；回呼裡用到可能還沒指派的欄位，null 參考例外只在高負載時出現；用 `Thread.Sleep` 讓順序「通常」正確。
- 為何有害：Lu 等人的研究中，約三分之一非死結並行 bug 是違反程式設計者的順序意圖，而且這種意圖不容易用鎖表達；73% 的非死結 bug 不是單純加鎖或改鎖就修好的。
- 解法：把順序變成明確的同步：先完成初始化，最後才啟動；用事件、`TaskCompletionSource`、屏障（barrier）等待前置步驟完成；`Join`／`await` 前置工作。
- 何時不算：同一條執行緒內的先後順序，程式順序本身就保證了。
- 來源：https://www.cs.columbia.edu/~junfeng/08fa-e6998/sched/readings/concurrency-bugs.pdf ；Farchi 等人的並行 bug 樣式分類「Interleavings Assumed Never to Occur」：https://research.ibm.com/publications/concurrent-bug-patterns-and-how-to-test-them 〔摘要〕

### Invariant Split Across Locks（同一個不變量被拆給不同鎖保護）
- 定義：兩個變數之間有必須一起成立的關係，也就是不變量（invariant），例如 `lower <= upper`、總數等於各項加總；但這兩個變數分別由不同的鎖保護。
- 辨識訊號：同一個類別有多個鎖物件；某方法在 lockA 下改 x、在 lockB 下改 y，而 x、y 有關聯；為了「降低鎖競爭」把一把鎖拆成多把之後，開始出現資料不一致。
- 為何有害：每個變數各自都安全，組合起來卻可能違反不變量。這是「鎖切太細」在正確性上的代價。
- 解法：JCIP 規則：凡是涉及多個變數的不變量，相關變數都必須由同一把鎖保護；或把相關變數封裝成一個不可變值物件，整體替換。
- 何時不算：變數彼此獨立，這正是拆鎖（lock splitting）的合法前提。
- 來源：JCIP 規則引文：https://www.cs.umd.edu/class/fall2010/cmsc433/lectures/thread-safety.pdf 〔摘要〕；https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/visibility-and-atomicity-vna/vna03-j

### Volatile as Synchronization（把 volatile 當同步工具）
- 定義：以為欄位加上 `volatile` 就執行緒安全了。
- 辨識訊號：`volatile` 欄位上出現 `++`、`+=` 或 check-then-act；`volatile` 參考指向的物件內容被多條執行緒修改；用 `volatile` 取代 `lock` 來保護多步操作。
- 為何有害：Microsoft 明說 `volatile` 除了賦值之外不提供原子性、不防止競爭條件（race condition）、也不保證其他記憶體操作的順序；在多處理器上，volatile 讀不保證拿到最新寫入的值。CERT 也指出宣告 volatile 無法保證複合操作的原子性。
- 解法：Microsoft 建議大多數情況改用 `Interlocked`、`lock`、`Volatile` 類別或更高階的同步原語。
- 何時不算：單一寫入者、多讀者的簡單「停止旗標」賦值，也就是 Microsoft 文件中的 `_shouldStop` 範例；低階程式碼的作者確實熟悉記憶體模型，並在註解中說明理由。
- 來源：https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/keywords/volatile ；https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/visibility-and-atomicity-vna/vna02-j

### Broken Double-Checked Locking（錯誤的雙重檢查鎖定）
- 定義：雙重檢查鎖定（double-checked locking, DCL）是為了省掉鎖的成本，先不加鎖檢查一次 null，再加鎖檢查一次，然後建立物件；錯在欄位沒有正確的記憶體可見性保證。
- 辨識訊號：`if (inst == null) { lock (l) { if (inst == null) inst = new X(); } }`，在 Java 裡 `inst` 沒宣告為 volatile；手刻 singleton 或延遲初始化的快取。
- 為何有害：初始化物件內容的寫入，和把參考寫進欄位的寫入，可能被編譯器或處理器重新排序；別的執行緒可能看到「參考已不是 null、但內容還沒初始化」的物件。這是 Pugh、Bloch、Lea 等人聯署宣言的結論。
- 解法：Java 把欄位宣告為 volatile（Java 5 以上才有效）或用 holder 類別延遲初始化；C# 用 `Lazy<T>`（預設 `ExecutionAndPublication` 模式，完全執行緒安全）或靜態初始化；或用 `Interlocked.CompareExchange`。CERT LCK10-J 要求只用正確形式。
- 何時不算：使用語言或平台保證正確的形式。DCL 在 .NET 上是否安全，取決於執行環境的記憶體模型〔未查證〕，不要自行判斷，直接用 `Lazy<T>`。
- 來源：https://www.cs.umd.edu/~pugh/java/memoryModel/DoubleCheckedLocking.html ；CERT LCK10-J：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/locking-lck/lck10-j ；https://learn.microsoft.com/dotnet/framework/performance/lazy-initialization 〔摘要〕

### Unsafe Publication（不安全發佈：物件還沒建好就被別的執行緒看到）
- 定義：物件還沒建構完成，參考就被別的執行緒拿到。
- 辨識訊號：建構子裡把 `this` 註冊到事件、static 清單，或啟動執行緒／Task 並把 `this` 傳出去；建構子內呼叫可被覆寫的虛擬方法；把剛 new 的物件寫進普通共享欄位，讓其他執行緒去讀。
- 為何有害：其他執行緒可能看到欄位還沒初始化的物件。Microsoft 另指出一個相關陷阱：類別的 static 建構子若啟動新執行緒、而新執行緒又呼叫該類別的 static 成員，新執行緒會被卡住，直到 static 建構子跑完。
- 解法：建構完成後才註冊或啟動，例如改用工廠方法，或把 `Start()` 從建構子分離出來；用安全手段交給其他執行緒，例如鎖、並行集合、`Volatile.Write`、靜態初始化。
- 何時不算：物件在建構它的同一條執行緒內用完，才交給別人。
- 來源：CERT TSM01-J「Do not let the this reference escape during object construction」、TSM02-J、TSM03-J：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/thread-safety-miscellaneous-tsm/ ；https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices

### Mutable Static State in Server Code（伺服器程式裡會被修改的 static 狀態）
- 定義：伺服器程式用 static 欄位存放會被修改的狀態。
- 辨識訊號：非 readonly 的 static 集合或欄位被 request handler 寫入；static 方法修改 static 狀態。
- 為何有害：Microsoft 指出，伺服器情境下 static 狀態跨請求共享，多條執行緒會同時執行那段程式碼，打開執行緒 bug 的大門；若加了同步，static 方法之間互相呼叫又可能死結，或重複同步拖慢效能。
- 解法：把資料封裝進不跨請求共享的實例，這是 Microsoft 的建議；真的要共享，就用專門設計的執行緒安全型別並集中管理。Microsoft 也建議 static 資料預設就要做成執行緒安全。
- 何時不算：`static readonly` 而且內容不可變，例如常數表；啟動時初始化、之後只讀。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices

## A2 鎖的設計

### Coarse-Grained Lock / One-Lane Bridge（鎖粒度過粗／單線橋）
- 定義：一把大鎖把所有呼叫者排成單線，而且持鎖期間還做大量工作。
- 辨識訊號：全域或 static 鎖包住整個方法；鎖內有 CPU 密集計算（雜湊、序列化、排序）或 I/O；增加 CPU 核心或執行緒，吞吐量卻不升；profiler 顯示大量執行緒在等同一把鎖，CPU 卻沒滿。
- 為何有害：One-Lane Bridge 是 Smith & Williams 的效能反模式：只有一個能前進，其他都得等。2026 年的實驗中，它把可用的並行能力變成序列化佇列，吞吐量大幅下降。
- 解法：縮小鎖範圍，只鎖真正共享狀態的讀寫，把計算與 I/O 移出鎖外。Goetz 指出整個方法加 synchronized 常常「只是圖方便」，並不是整個方法都需要同步。也可以拆鎖或分段鎖（lock splitting／lock striping，不同資料用不同的鎖，見 JCIP 第 11 章）；改用並行集合或不可變快照；讀多寫少用讀寫鎖。
- 何時不算：使用量低、鎖內工作極短。Smith 明說程式裡有 One-Lane Bridge，但使用量夠低時不構成效能問題。正確性優先、而且量測顯示沒有鎖競爭時也不算。
- 來源：https://arxiv.org/abs/2602.12079 ；https://research.spec.org/icpe_proceedings/2020/proceedings/p173.pdf ；https://www.infoworld.com/article/2075692/avoid-synchronization-deadlocks.html ；JCIP 第 11 章講義：https://www.cs.umd.edu/class/fall2010/cmsc433/lectures/jcip-ch11.pdf 〔摘要，原檔 403〕

### Over-Synchronization（過度同步／鎖切得過細）
- 定義：不需要同步的地方也加鎖，或把鎖切得很碎，一個操作要拿好幾把鎖。
- 辨識訊號：每個 getter／setter 都 lock；只在單執行緒使用的類別內部也全是鎖；一個操作要連續取得 3 把以上的鎖；用 `lock` 保護單一計數器遞增；鎖物件的數量比需要保護的不變量還多。
- 為何有害：Microsoft 指出不必要的同步會降低效能，並帶來死結與競爭條件的可能；加鎖會增加鎖競爭。鎖越多，鎖順序越難維持（見〔Inconsistent Lock Ordering〕）。能源壞味道分類 C11 也把過度鎖競爭列為耗能來源。
- 解法：先問「這真的有被共享嗎」。Microsoft 建議實例資料預設不要做成執行緒安全，由呼叫端負責；單一變數的簡單狀態改用 `Interlocked`；把相關資料合併到同一把鎖下（同時滿足〔Invariant Split Across Locks〕）。
- 何時不算：公開給多執行緒使用的程式庫 API，Microsoft 建議其 static 資料預設要執行緒安全；量測證明拆鎖有效，而且沒有不變量跨鎖。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices ；https://arxiv.org/abs/2604.04809

### Inconsistent Lock Ordering（巢狀鎖的取得順序不一致）
- 定義：兩段程式以不同順序取得同一組鎖，結果互相等對方放手。
- 辨識訊號：一處寫 `lock(a){ lock(b){…} }`，另一處寫 `lock(b){ lock(a){…} }`；依參數決定鎖誰，例如轉帳 `Transfer(from, to)` 先鎖 from 再鎖 to，兩個方向同時轉帳就互鎖；卡死時的 thread dump 顯示兩條執行緒各持一把鎖、等另一把；系統「偶爾卡死、重啟就好」。
- 為何有害：會死結（deadlock）。Lu 等人的研究中，97% 的死結 bug 是兩條執行緒循環等待最多兩個資源。
- 解法：全程式固定取鎖順序，例如依物件 ID 由小到大（CERT LCK07-J）；用有逾時的嘗試取鎖（`Monitor.TryEnter(obj, 300)`／`tryLock`），失敗就放掉已拿的鎖再重試；把需要多把鎖的操作改成單鎖或無鎖設計；把鎖順序寫進文件（Goetz）。
- 何時不算：只有一把鎖；有巢狀鎖，但全程式只有一種順序，而且有文件記載。
- 來源：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/locking-lck/lck07-j ；https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices ；https://www.infoworld.com/article/2075692/avoid-synchronization-deadlocks.html ；https://www.cs.columbia.edu/~junfeng/08fa-e6998/sched/readings/concurrency-bugs.pdf

### Calling Alien Methods While Holding a Lock（持鎖時呼叫外部程式碼）
- 定義：持鎖期間呼叫自己掌控不了行為的程式碼，也就是外來方法（alien method），例如事件、回呼、委派、虛擬方法、介面實作、插件。
- 辨識訊號：`lock` 區塊內觸發事件、呼叫 `Action`／`Func` 參數、呼叫 `listener.OnXxx()`、呼叫可被覆寫的方法或其他元件的公開方法。
- 為何有害：外部程式碼可能再去取別的鎖，造成鎖順序反轉而死結；可能回頭呼叫本物件，重入時改壞狀態；也可能很慢，變成〔Blocking While Holding a Lock〕。Goetz 舉的例子是 Model 持著自己的鎖去呼叫 `View.somethingChanged()`。Bloch 把這類方法稱為 alien method，建議在同步區外呼叫，這種呼叫叫做開放呼叫（open call）。
- 解法：在鎖內複製需要的資料，例如 listener 清單的快照，出鎖後再呼叫；事件也是先取快照、出鎖後才觸發。
- 何時不算：被呼叫的是同模組內、行為已知、不取鎖、不回呼的私有方法。
- 來源：https://www.infoworld.com/article/2075692/avoid-synchronization-deadlocks.html ；Bloch 的 open call 說法〔摘要，Effective Java 原書未查〕

### Blocking While Holding a Lock（持鎖時做阻塞操作）
- 定義：持著鎖去做 I/O、睡眠或等待其他事件。
- 辨識訊號：鎖內有網路、檔案、資料庫、主控台的讀寫、`Thread.Sleep`、同步等待 Task 結果、物件序列化。
- 為何有害：CERT LCK09-J 指出，持鎖做耗時或阻塞操作會嚴重降低效能，並可能造成飢餓（starvation，某些執行緒一直拿不到資源）；其他執行緒全部卡在鎖外。CERT 列舉的阻塞操作包括網路、檔案、主控台 I/O、物件序列化，以及無限期延遲執行緒。
- 解法：CERT 的做法是在鎖內只做共享資料的同步操作、複製要送出的資料，阻塞 I/O 移到鎖外；需要等條件時，用會釋放鎖的等待（`Monitor.Wait`／`Object.wait`），不要用 sleep。
- 何時不算：鎖本身就是為了序列化對該 I/O 資源的存取，例如多執行緒寫同一個檔案，而且吞吐量不是需求；但要明寫出來，並限制持鎖時間。
- 來源：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/locking-lck/lck09-j

### Locking on Publicly Accessible Objects（拿外部也拿得到的物件當鎖）
- 定義：用 `this`、`typeof(X)`、字串常值、公開欄位這類外部程式碼也能拿到的物件當鎖。
- 辨識訊號：`lock(this)`、`lock(typeof(X))`、`lock("name")`；鎖公開屬性；鎖一個對外公開的集合本身。
- 為何有害：Microsoft 指出，每個型別在一個應用程式定義域裡只有一個 `Type` 物件，若該型別是公開的，別人也能鎖它，就可能死結；`lock(this)` 時若外部程式碼也鎖了這個物件，同樣可能死結。CERT 要求用私有、final 的鎖物件，並且不要鎖可能被重用的物件，例如被 intern 的字串或 boxing 後的值。
- 解法：用私有、唯讀、專用的鎖物件；.NET 9／C# 13 起可用 `System.Threading.Lock`。
- 何時不算：類別明確在文件中提供給呼叫端做 client-side locking 的物件。但 CERT LCK11-J 提醒，類別若沒有承諾其鎖策略，就要避免 client-side locking。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices ；CERT LCK00-J、LCK01-J、LCK11-J：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/locking-lck/

### Lock Not Released on Exception（例外路徑沒有釋放鎖）
- 定義：手動取得與釋放鎖時，發生例外就沒走到釋放那一步。
- 辨識訊號：`Monitor.Enter(x); DoWork(); Monitor.Exit(x);` 沒包 try/finally；`ReentrantLock.lock()` 之後沒有 `finally { unlock(); }`；`SemaphoreSlim.Wait()` 之後沒有 `finally { Release(); }`。
- 為何有害：一次例外就讓鎖永遠被佔住，之後所有等待者都卡死。
- 解法：C# 的 `lock` 陳述式會自動用 finally 呼叫 `Monitor.Exit`（Microsoft）；手動 API 一律 try/finally。Microsoft 另建議，若無法保證 Exit 會被呼叫，可考慮改用 `Mutex`，因為擁有它的執行緒結束時會自動釋放。
- 何時不算：使用會自動釋放的語言結構，例如 `lock`、`using`。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices ；CERT LCK08-J「Ensure actively held locks are released on exceptional conditions」：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/locking-lck/lck08-j

## A3 等待與通知

### Busy Waiting / Sleep Polling（忙等／睡眠輪詢）
- 定義：用迴圈反覆檢查條件來等某件事發生，而不是讓執行緒睡著、等別人通知。
- 辨識訊號：`while (!done) { }`、`while (!done) Thread.Sleep(10);`、`while (queue.Count == 0) ;`；執行緒「在等」，CPU 使用率卻居高不下；輪詢間隔是寫死的魔術數字。
- 為何有害：多數情況下自旋被視為反模式，處理器時間浪費在無用的活動上。用 sleep 輪詢則兩頭落空：間隔太短浪費 CPU，太長增加延遲。實作層的效能反模式「Spin Wait」（Boroday 等人，2005）指的就是這件事。
- 解法：改用阻塞原語，例如 `ManualResetEventSlim`、`SemaphoreSlim`、`Monitor.Wait/Pulse`、`BlockingCollection`／`Channel`、`TaskCompletionSource`；或改成回呼／通知模型。
- 何時不算：確定極短的等待，用專門的自旋原語（如 `SpinWait`、`SpinLock`）並有量測支持；有上限、有退避（backoff，每次失敗後拉長等待間隔）的重試迴圈。
- 來源：https://en.wikipedia.org/wiki/Busy_waiting 〔摘要〕；https://detectors.xygeni.io/xydocs/quality/detectors/java/java.sleep_in_loop_busy_wait.html 〔摘要〕；Spin Wait 歸類見 https://arxiv.org/abs/1508.04752

### Condition Wait Without Loop / Lost Notification（條件等待不在迴圈內／通知遺失）
- 定義：等待條件時只檢查一次（用 `if` 而不是 `while`），或通知在對方開始等待之前就發出而遺失。
- 辨識訊號：`if (!ready) Monitor.Wait(l);`（應該用 `while`）；多種條件共用同一個監視器，卻只喚醒單一等待者（`Pulse`／`notify`）；通知可能比等待早發生，卻沒有記住「已通知」的狀態。
- 為何有害：被喚醒時，條件可能已經不成立，例如被別的執行緒先搶走，繼續執行就違反前提；通知遺失則會永遠等下去。
- 解法：CERT THI03-J 要求 wait／await 一律放在迴圈內重新檢查條件；THI02-J 要求通知所有等待者（`PulseAll`／`notifyAll`）而不是單一個；優先用 `BlockingCollection`、`Channel`、`SemaphoreSlim` 這類高階結構，避免手寫條件變數。
- 何時不算：使用高階並行結構時，這個迴圈已經由框架處理。
- 來源：CERT THI02-J、THI03-J（規則標題已核對，內文理由未逐字核對）：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/thread-apis-thi/ ；Farchi 等人的「Losing a Notify」樣式：https://research.ibm.com/publications/concurrent-bug-patterns-and-how-to-test-them 〔摘要〕

## A4 執行緒數量與生命週期

### Thread-per-Request（每個請求開一條執行緒）
- 定義：每來一個請求就 new 一條執行緒處理，沒有上限。
- 辨識訊號：請求或連線處理迴圈內有 `new Thread(...).Start()`；執行緒數隨負載線性上升；尖峰時記憶體與 context switch（CPU 在執行緒間切換）暴增，系統直接無回應，而不是逐步變慢。
- 為何有害：CERT TPS00-J 指出，攻擊者可以用大量請求造成阻斷服務，系統變得無回應而不是優雅降級；還有執行緒建立、排程、配置與頻繁 context switch 的開銷。
- 解法：用執行緒池或有上限的並行，例如固定大小的 ExecutorService、.NET ThreadPool／Task、`SemaphoreSlim` 限流；I/O 密集的工作改用非同步 I/O，不佔住執行緒。
- 何時不算：數量天生有上限而且很小，例如固定 N 個長駐背景 worker；Microsoft 也認為不同資源（I/O、使用者輸入）各用一條專用執行緒是合理的。
- 來源：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/thread-pools-tps/tps00-j ；https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices

### More Is Less（越多越慢：執行緒或池資源配置過量）
- 定義：某種資源配置過多，例如執行緒、行程、池中的連線，反而拖慢整體。
- 辨識訊號：執行緒數遠多於 CPU 核心數，而且多為 CPU 密集工作；提高平行度後吞吐量反而下降；profiler 顯示大量時間花在排程與同步。Smith 提醒，profiler 不會直接顯示作業系統開銷，所以這個問題常常看不出來。
- 為何有害：Smith 指出，多出的執行緒在少核心平台上不會增加並行度，只會增加排程、分派、context switch、通訊，甚至 page fault 的開銷。2026 年的實驗中，增加執行緒數後，排程、同步與資源競爭的開銷超過效益，吞吐量下降。
- 解法：CPU 密集工作的平行度以 `Environment.ProcessorCount` 為基準；用執行緒池，不要自己建；量測後再調整池大小。
- 何時不算：以 I/O 等待為主的工作，較多並行可以掩蓋延遲，但優先用非同步 I/O。
- 來源：https://research.spec.org/icpe_proceedings/2020/proceedings/p173.pdf ；https://arxiv.org/abs/2602.12079 ；https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices

### Thread Leak（執行緒洩漏）
- 定義：持續啟動新執行緒或建立新的執行緒池，卻從不停止。
- 辨識訊號：行程的執行緒數只升不降；每次呼叫某方法就建立新的 Executor、Timer 或背景迴圈，卻沒有 shutdown／Dispose；thread dump 裡有大量同名、閒置、停在 park／wait 的 worker。
- 為何有害：每條執行緒都佔堆疊記憶體，無上限地啟動執行緒就是一種記憶體洩漏，最後記憶體不足（OOM）。
- 解法：執行緒池與計時器做成長生命週期的單例，關閉應用程式時才 shutdown／Dispose；背景迴圈支援取消（`CancellationToken`）；監控執行緒數。
- 何時不算：數量有上限的長駐 worker。
- 來源：https://www.morling.dev/blog/finding-java-thread-leaks-with-jdk-flight-recorder-and-bit-of-sql/ 〔摘要〕；https://blog.gceasy.io/memory-leak-in-java-executor/ 〔摘要〕

### Interdependent Tasks in a Bounded Pool（有上限的池中放了互相等待的任務）
- 定義：在固定大小的執行緒池裡，任務同步等待另一個也排在同一個池的任務，造成執行緒飢餓死結（thread starvation deadlock）。
- 辨識訊號：池內任務用 `.Result`／`.Wait()`／`Future.get()` 等待子任務；池滿載時整體停止推進，CPU 使用率卻很低。在 .NET 裡，同步等待非同步工作（sync over async）就是這種形狀，細節見 [03-csharp-dotnet.md](03-csharp-dotnet.md)。
- 為何有害：所有工作執行緒都在等，而它們等的任務排在佇列中，分不到執行緒，結果死結或嚴重延遲。
- 解法：CERT TPS01-J：不要在有界池中執行互相依賴的任務；改成非同步組合（`await`、continuation）；或把相依的任務放到不同的池。
- 何時不算：子任務不走同一個池。池沒有上限也不會死結，但那會變成〔Thread-per-Request〕的問題。
- 來源：CERT TPS01-J「Do not execute interdependent tasks in a bounded thread pool」：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/thread-pools-tps/

### Forcible Thread Termination（從外部強制終止執行緒）
- 定義：從外部硬殺或硬停另一條執行緒。
- 辨識訊號：`Thread.Abort`、`Thread.Suspend`／`Resume`、Java `Thread.stop()`、Win32 `TerminateThread`。
- 為何有害：Microsoft 說明，Abort 等於在對方不知道執行到哪裡時對它丟例外；.NET 5 起 `Thread.Abort` 已過時，呼叫會丟 `PlatformNotSupportedException`。被殺的執行緒可能留下沒釋放的鎖和改到一半的狀態。
- 解法：用協作式取消（`CancellationToken`）；CERT THI05-J 也禁止用 `Thread.stop()`。
- 何時不算：整個行程本來就要結束。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices ；CERT THI05-J：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/thread-apis-thi/

### Stale ThreadLocal in Pooled Threads（池化執行緒中殘留的 ThreadLocal）
- 定義：在執行緒池裡使用執行緒區域變數（ThreadLocal／`[ThreadStatic]`），任務結束時沒清掉，下一個任務就拿到上一個任務的值。
- 辨識訊號：ThreadLocal 設值後沒有在 finally 清除；請求之間出現「別人的資料」；記憶體被 ThreadLocal 長期佔住。
- 為何有害：池裡的執行緒會被重複使用，殘留的值會造成資料外洩或錯誤結果，也會延長物件的存活時間。
- 解法：CERT TPS04-J：使用執行緒池時要重新初始化 ThreadLocal；在 finally 清除；或改成顯式傳參。
- 何時不算：值本身不含請求資料、可安全共用，例如每條執行緒一個重用的緩衝區。
- 來源：CERT TPS04-J「Ensure ThreadLocal variables are reinitialized when using thread pools」：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/thread-pools-tps/

---

# B. 效能（Performance）

## B1 白做的工

### Unnecessary Processing（不必要的處理）
- 定義：在關鍵路徑上做了此刻不需要、或根本不需要的工作。
- 辨識訊號：算出來的結果沒人用；啟動時建立大量之後才用、甚至從不使用的物件或畫面。Smith 的實例是啟動時建立約 30 個畫面，最貴的一個要 9 秒，而且很少用到。還有重複驗證、重複排序。
- 為何有害：拖慢回應。2026 年的實驗發現，這個反模式的回應時間不一定明顯變差，但 CPU 與記憶體（DRAM）的功耗被白白消耗，DRAM 能耗是十種反模式中最高的。
- 解法：刪掉沒用的工作；延後到需要時才做（lazy），或在閒置時段做。Smith 指出總工作量不變，但回應性會改善。
- 何時不算：刻意的預熱（warm-up），用啟動成本換取之後穩定的延遲，而且有量測支持。
- 來源：https://research.spec.org/icpe_proceedings/2020/proceedings/p173.pdf （§4.1）；https://arxiv.org/abs/2602.12079

### Repeated Computation / "How Many Times Do I Have to Tell You?"（重複計算）
- 定義：同樣的結果在迴圈內、或在多條呼叫路徑上被重算很多次。
- 辨識訊號：迴圈內呼叫結果不隨迭代改變的函式（迴圈不變量），例如每圈都對 IEnumerable 呼叫 LINQ `Count()`、每圈重新編譯同一個 Regex、每圈重讀設定；profiler 顯示某個共用方法的呼叫次數遠超預期。Smith 的偵測法是量每個方法的呼叫次數，再追查是誰在呼叫。
- 為何有害：Smith 的實例中，移除重複呼叫後該情境的處理時間降了 80%。能源壞味道分類把它歸在 C1 Redundant Computation 與 C8 Missing Reuse。
- 解法：把不變量提到迴圈外；在呼叫樹的上層算一次再往下傳；把昂貴的結果快取起來（注意〔Over-Caching〕與〔Cache Without Invalidation〕）。
- 何時不算：編譯器或 JIT 會自動提出迴圈的簡單運算，例如陣列的 `Length`；重算成本極低，而快取反而會帶來一致性問題。
- 來源：https://research.spec.org/icpe_proceedings/2020/proceedings/p173.pdf （§4.2）；https://arxiv.org/abs/2604.04809

### Tower of Babel / Repeated Serialization（巴別塔：反覆轉換格式與序列化）
- 定義：資料在元件之間傳遞時一再轉換格式，例如物件→JSON→物件→XML，大量時間花在轉換上。
- 辨識訊號：同一個請求內，對同一份資料序列化／反序列化多次；字串和數字、日期之間反覆轉換；profiler 中序列化器、`Parse`、`ToString` 佔比很高；每一層各自定義 DTO（資料傳輸物件）並互相轉換。
- 為何有害：Cortellessa 等人的定義是「行程使用不同的資料格式，花太多時間轉換成內部格式」。2026 年實驗的高耗 CPU 實作中也包含反覆的 JSON 轉換（JSON churn）。
- 解法：只在邊界轉換一次，內部統一用同一種表示；傳遞已解析好的物件，而不是字串；必要時快取序列化結果。
- 何時不算：跨信任邊界或跨版本的明確契約轉換，安全驗證與相容性比效能重要。
- 來源：https://arxiv.org/abs/2301.09531 （Table 1）；https://arxiv.org/abs/2602.12079 （Table II）

### Unnecessary Deep Copy（不必要的深拷貝）
- 定義：為了「安全」把整個物件圖複製一份，但呼叫端其實不會修改，或根本不需要獨立的副本。
- 辨識訊號：每次讀取都 `Clone()`，或用序列化再反序列化來做深拷貝；getter 每次回傳整個集合的新副本，又在迴圈內被呼叫；配置 profiler 中拷貝函式名列前茅。
- 為何有害：增加配置量與 GC 壓力。能源壞味道 C6 的定義是「配置、複製或保留超過工作需要的記憶體」，研究也發現記憶體類壞味道每次修復省下的能耗最多。2026 年實驗中的 Unnecessary Processing 實作也包含深拷貝。
- 解法：回傳唯讀視圖（`IReadOnlyList`、`ReadOnlySpan`）或不可變物件；寫入時才複製（copy-on-write）；只拷貝要修改的部分。
- 何時不算：跨執行緒或跨信任邊界的防禦性複製，用來防止外部修改破壞內部不變量，正確性優先。
- 來源：https://arxiv.org/abs/2604.04809 ；https://arxiv.org/abs/2602.12079 （Table II）

## B2 演算法與成長

### Hidden Quadratic（隱藏的 O(n²)）
- 定義：看起來是線性的程式碼，因為在迴圈內呼叫了本身就是 O(n) 的操作，整體變成 O(n²)。
- 辨識訊號：迴圈內有 `List.Contains`／`IndexOf`／`Remove(item)`／`RemoveAt(0)`／`Insert(0, …)`；迴圈內用 `+=` 串接字串；用巢狀迴圈在兩份清單間「找對應」；資料量翻倍，時間變四倍。
- 為何有害：小測試資料看不出來，上線後資料量一大就爆。「Accidentally Quadratic」部落格收錄的真實案例包括：Mercurial 對 Python list 做成員測試、Ruby `reject!` 每刪一個元素就花 O(n)、C# 常數摺疊時的字串串接。
- 解法：先建 `HashSet`／`Dictionary` 索引再查；用 `StringBuilder`；批次刪除（`RemoveAll`，或過濾成新集合）；排序後合併。
- 何時不算：n 有小而固定的上限（例如最多數十個），並有註解說明。
- 來源：https://accidentallyquadratic.tumblr.com/ ；https://arxiv.org/abs/2604.04809 （C5 資料結構不合、C7 演算法）

### The Ramp（斜坡：隨使用時間與資料量越來越慢）
- 定義：處理時間隨系統使用時間或資料量增長而持續上升。
- 辨識訊號：同一個操作的延遲隨上線天數穩定爬升；重啟後變快、之後又慢；資料表或記憶體集合只增不減，每個請求卻都線性掃描它（2026 年實驗的實作就是在不斷變長的清單上做線性搜尋）。Smith 提醒，測試資料量不夠時偵測不到。
- 為何有害：Smith 指出處理時間線性增加時，回應時間會呈指數增加；2026 年實驗中，它讓回應時間與功耗一起上升。
- 解法：換資料結構或演算法（索引、分區、分頁）；限制工作集，例如只載入今天要處理的資料、讓使用者輸入篩選條件而不是列出全部；清理歷史資料。
- 何時不算：成長有天然上限，而且已在容量規劃內。
- 來源：https://research.spec.org/icpe_proceedings/2020/proceedings/p173.pdf （§4.4）；https://arxiv.org/abs/2602.12079

## B3 I/O 往返

### Circuitous Treasure Hunt / N+1 Query（迂迴尋寶／N+1 查詢）
- 定義：為了湊齊一份資料，查完一筆再根據結果查下一筆，層層往下，造成大量往返。
- 辨識訊號：迴圈內查資料庫或呼叫 API（例如 `foreach order` 再查 details）；ORM 延遲載入（lazy loading）讓一個頁面發出數十、上百條 SQL；一次請求中同一條 SQL 樣板執行了 N 次。Azure 的範例中，一個方法就發出 45 條 SELECT。
- 為何有害：Smith & Williams 的定義是資料要從很多地方、以很高的查找成本收集。2026 年實驗指出，巢狀的連續查詢造成大量往返、妨礙查詢最佳化、強迫序列執行。Azure 提醒 ORM 可能把這個問題藏起來，也就是所謂的 N+1 問題。
- 解法：一次查詢帶回，例如 JOIN、`Include`（eager loading，預先載入）、用 IN 子句批次查；在服務端組好資料；快取查找表。
- 何時不算：N 很小而且固定；或分開查能利用快取，而 JOIN 反而更貴，以量測為準。
- 來源：https://arxiv.org/abs/2602.12079 ；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/chatty-io/

### Empty Semi Trucks / Chatty I/O（空車半掛：請求太多、每次只運一點）
- 定義：完成一件事需要過多次請求，每次只搬一點點資料。
- 辨識訊號：逐筆寫入資料庫或檔案；一個邏輯操作拆成多個 HTTP 呼叫，例如每個屬性一個 GET；大量小封包。Azure 列的偵測訊號：對同一檔案、服務或資料存放區的大量小請求；應用程式變成 I/O bound（瓶頸在 I/O）。
- 為何有害：每次 I/O 都有固定開銷，累積起來拖垮延遲與吞吐量。Azure 的範例改成單一查詢後，每分鐘處理的請求數從 410 升到 3,970。
- 解法：打包成較少、較大的請求，例如批次 API、bulk insert、先緩衝再一次寫入；API 設計成粗粒度。
- 何時不算：批次太大會變成〔Sisyphus Database Retrieval〕，或拉長單次延遲；即時性要求高的串流也不適合批次。Azure 提醒，先緩衝在記憶體再寫入的資料，行程當機時可能遺失。
- 來源：https://arxiv.org/abs/2301.09531 （Table 1）；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/chatty-io/

### Sisyphus Database Retrieval / Extraneous Fetching（撈回比需要多得多的資料）
- 定義：查回遠多於需要的資料，再在應用程式內丟掉大部分。
- 辨識訊號：`SELECT *`；先把整張表 `ToList()`，再在記憶體裡做 `Where`／`Skip`／`Take`；分頁在應用層做；回應的資料量遠大於畫面實際用到的欄位。
- 為何有害：2026 年實驗的實作是每個請求都全表掃描並 JOIN、為每一列建立物件，最後只回傳一小部分；浪費會隨資料量放大。Azure 的 Extraneous Fetching 指的是取回多於需要的資料、造成不必要的 I/O。
- 解法：在資料來源端篩選、只選需要的欄位（projection）、在來源端分頁。
- 何時不算：資料量小，而且整批快取後會被重複使用。
- 來源：https://arxiv.org/abs/2602.12079 ；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/ ；SPEC RG 指出此反模式由 Dugan 等人（2002）定義：https://arxiv.org/abs/1508.04752

## B4 配置與實例化

### Excessive Dynamic Allocation（過度動態配置：熱路徑大量建立短命物件）
- 定義：在熱路徑上大量建立、又立刻丟棄短命物件。
- 辨識訊號：緊密迴圈內 new List／Dictionary、串接字串、LINQ 產生暫存物件、建立閉包、值型別 boxing；配置 profiler 顯示某個方法的配置量最大；GC 次數高，GC 暫停時間佔比高。
- 為何有害：Smith & Williams 的定義是「太多短命物件被建立又銷毀」。2026 年實驗中，它是十種反模式裡 CPU 能耗最高的。
- 解法：重用緩衝區（例如 `ArrayPool`，或物件池，見〔Object Pool Misuse〕）；在迴圈外配置一次；避免 boxing；C# 的 `Span`、`stackalloc` 等細節見 [03-csharp-dotnet.md](03-csharp-dotnet.md)。
- 何時不算：不在熱路徑上。現代分代式 GC 處理短命小物件很便宜，沒有量測證據前，不必為此犧牲可讀性（見〔Premature Optimization〕）。
- 來源：https://arxiv.org/abs/2602.12079

### Improper Instantiation（不當實例化：該共用的物件每次都重建）
- 定義：設計成「建立一次、到處共用」的物件，例如連線或客戶端類別，卻在每個請求中重新建立。
- 辨識訊號：每個請求都 `using var client = new HttpClient()`；每次呼叫都新建資料庫、Redis 或訊息佇列的 client。Azure 列的偵測訊號：資源耗盡類例外增加（socket、連線、檔案 handle）、記憶體與 GC 增加、網路／磁碟／資料庫活動增加。
- 為何有害：Azure 指出，高負載下會耗盡 socket，丟出 `SocketException`；建立成本高的物件會壓低吞吐量，範例中平均回應時間變為 20 倍。
- 解法：用執行緒安全的共用單例或物件池；.NET 用 `IHttpClientFactory`；不要在每個請求中修改共用物件的屬性，例如 `DefaultRequestHeaders`，會產生競爭條件。
- 何時不算：類別本身不能共用（非執行緒安全）。稀缺資源如資料庫連線不應長期佔住（Azure 的提醒），這種情況要用連線池，而不是共用一條長連線。
- 來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/improper-instantiation/

## B5 負載與排隊

### Blob / God Class — performance view（團塊／上帝類別：效能視角）
- 定義：單一元件做了系統大部分的工作，或握有大部分的資料，所有請求都要經過它。
- 辨識訊號：一個類別或服務包辦驗證、記錄、快取、儲存、雜湊等所有責任；大部分訊息流量進出同一個元件；該元件的 CPU 用量或佇列長度遠高於其他元件。
- 為何有害：產生過多訊息流量並成為瓶頸。2026 年實驗的實作中，每次呼叫都開新的資料庫連線、I/O 被迫序列化。
- 解法：拆分責任，把資料與操作放在一起，減少來回取資料；把過載元件複製多份分攤負載（clone）。
- 何時不算：結構上是 God Class，但不在熱路徑上。那是可維護性問題（見 [01-classic-catalog.md](01-classic-catalog.md)、[02-design-architecture.md](02-design-architecture.md)），不是效能問題。
- 來源：https://arxiv.org/abs/2301.09531 （Table 1）；https://arxiv.org/abs/2602.12079

### Unbalanced Processing / Pipe and Filter（處理不平衡／最慢的一段卡住整條管線）
- 定義：處理沒有用到可用的處理器，或某一個慢階段限制了整體吞吐量。
- 辨識訊號：多階段管線中，某一段的佇列持續堆積，其他段卻閒置；多核心機器上只有一個核心滿載；CPU 密集工作直接在請求執行緒上同步執行（2026 年實驗的實作即是如此）。
- 為何有害：吞吐量被最慢的階段鎖死。Pipe and Filter 反模式的定義是：最慢的 filter 讓系統吞吐量低到無法接受。
- 解法：平行化或複製慢的階段；把重工作移到背景或獨立服務；重新分配負載；讓短任務有較高的優先權，這是 Extensive Processing 反模式的解法。
- 何時不算：順序有業務語義、必須序列執行，例如同一個帳戶的交易。
- 來源：https://arxiv.org/abs/2602.12079 （Table I）；https://arxiv.org/abs/2301.09531 ；優先權解法〔摘要〕

### Traffic Jam（塞車：一次暫時問題造成長時間積壓）
- 定義：一個暫時性的問題造成工作積壓，問題消失後，回應時間仍長時間偏高，而且波動很大。
- 辨識訊號：尖峰或某次慢操作之後，p99 延遲（最慢 1% 請求的延遲）要好幾分鐘才恢復；佇列長度曲線有長尾；定時的批次重工作與線上流量擠在同一時段。
- 為何有害：積壓的等待時間會拉高之後正常請求的回應時間（2026 年實驗）；也造成回應時間變異很大（Cortellessa 等人）。
- 解法：錯開重工作的時段，或移到獨立資源；限流與背壓（backpressure，用有上限的佇列，滿了就拒絕或降級）；擴充容量應付尖峰。
- 何時不算：可以接受批次延遲，而且沒有服務水準要求（SLA）。
- 來源：https://arxiv.org/abs/2602.12079 ；https://arxiv.org/abs/1404.0851

### Falling Dominoes / Retry Storm（骨牌效應／重試風暴）
- 定義：一個元件失敗，連帶引發其他元件的效能失敗。常見機制是大量、立即、沒有上限的重試。
- 辨識訊號：沒有退避的重試迴圈；重試次數沒有上限；某個下游掛掉時，上游的 CPU 用量與錯誤處理時間暴增。Smith 的實例是一個接收端反覆要求重傳，拖慢了整個系統。
- 為何有害：被重試打的服務更難恢復（Azure Retry Storm），故障會擴散開來。
- 解法：Azure 建議限制重試次數、指數退避、使用斷路器（Circuit Breaker，失敗達門檻就暫停呼叫）、遵守 `Retry-After` 回應標頭。Smith 建議把故障元件隔離到修好為止，並監控「錯誤處理／有用工作」的比例，達門檻就停用失敗元件。
- 何時不算：冪等（重做不會改變結果）、低頻、而且已有退避與上限的重試。
- 來源：https://research.spec.org/icpe_proceedings/2020/proceedings/p173.pdf （§4.6）；https://learn.microsoft.com/en-us/azure/architecture/antipatterns/retry-storm/ 〔摘要〕

### Are We There Yet? / Is Everything OK?（到了沒？：過度輪詢與狀態檢查）
- 定義：檢查事件或平台狀態（電量、磁碟空間等）的頻率遠高於它實際變化的頻率；也包括過度頻繁地寫狀態 log。
- 辨識訊號：Timer 間隔遠小於狀態變化的週期；背景執行緒每秒檢查很少變動的東西；輪詢迴圈每一輪都寫 log。
- 為何有害：Smith 指出，喚醒和排程的開銷常常比檢查本身還大，有時還伴隨動態建立、銷毀執行緒；過度頻繁記錄狀態也是較少被注意到的效能問題。
- 解法：改成事件通知（push）；把間隔拉長到符合實際變化頻率；log 改由應用邏輯決定要不要記，並且非同步寫入（Smith）。
- 何時不算：外部系統沒有通知機制可用，而輪詢間隔已依變化頻率調整過。
- 來源：https://research.spec.org/icpe_proceedings/2020/proceedings/p173.pdf （§3.1–3.2，Smith 2020 新增的反模式）

## B6 最佳化判斷本身出錯

### Premature Optimization（過早最佳化）
- 定義：還沒量測證明是瓶頸，就為了速度犧牲可讀性或正確性。
- 辨識訊號：沒附 benchmark 或 profile 數據的「優化」提交；非熱路徑上出現手刻快取、物件池、無鎖結構、位元操作技巧；註解寫「為了效能」卻沒有數字；為省幾奈秒而複製程式碼。
- 為何有害：Knuth 指出，程式設計師花大量時間擔心非關鍵部分的速度，這些嘗試對除錯與維護有強烈的負面影響。手刻的最佳化也常帶進並行 bug，例如〔Broken Double-Checked Locking〕。
- 解法：先量測，找出 Knuth 說的「關鍵的 3%」，只優化那裡；把量測數據留在 PR 或註解中。
- 何時不算：Knuth 原文的下一句是「但不該錯過那關鍵 3% 的機會」。已被量測證實的熱點，以及架構層級的效能決策（演算法、資料存取方式、I/O 次數）本來就該在設計時考慮，不算過早。不要拿這句話合理化〔Hidden Quadratic〕或〔Circuitous Treasure Hunt〕。
- 來源：Knuth（1974）〈Structured Programming with go to Statements〉，引文與上下文見 https://probablydance.com/2025/06/19/revisiting-knuths-premature-optimization-paper/

### Over-Caching（過度快取）
- 定義：快取了不值得快取的東西，或快取層疊得太多。
- 辨識訊號：快取命中率低（要量測）；從快取取值的成本不低於重算；同一份資料存在多層快取（記憶體、分散式、HTTP），各層失效時機不同步；為每一種使用者輸入都建快取項。
- 為何有害：佔用記憶體（見〔Unbounded Cache〕），增加資料一致性問題（見〔Cache Without Invalidation〕、〔Duplicated State〕），也增加程式複雜度。類比 Microsoft 對物件池的說法：除非初始化成本高，從池裡取物件通常更慢。
- 解法：只快取「昂貴而且會重複讀」的資料，並量測命中率；設大小上限與過期時間。
- 何時不算：量測證明是熱點，而且命中率高。
- 來源：〔未查證：找不到專門定義此味道的權威來源，本條由下列來源推論〕https://learn.microsoft.com/en-us/aspnet/core/performance/objectpool ；https://learn.microsoft.com/aspnet/core/performance/caching/memory 〔摘要〕

### Cache Without Invalidation（沒有失效策略的快取）
- 定義：快取了資料，卻沒定義資料何時過期，或來源改變時怎麼讓快取失效。
- 辨識訊號：快取寫入沒有過期時間；修改來源資料的程式路徑沒有對應的失效或更新；多台機器各自有本地快取；使用者回報「改了要過一陣子／重啟才看得到」。
- 為何有害：讀到過時的資料（stale data），導致錯誤決策。Phil Karlton 的名言：電腦科學只有兩件難事——快取失效與命名。
- 解法：明確的過期策略（絕對過期或滑動過期）；寫入來源時同步讓快取失效或更新；用版本號或 ETag；寫明每個快取能容忍多舊的資料。Microsoft 的記憶體快取文件也建議用過期來限制快取成長。
- 何時不算：資料不可變，例如以內容雜湊當鍵；業務明確接受固定時間內的過時資料。
- 來源：https://martinfowler.com/bliki/TwoHardThings.html ；https://learn.microsoft.com/aspnet/core/performance/caching/memory 〔摘要〕

---

# C. 記憶體與資源（Memory & Resource）

## C1 記憶體洩漏

> GC 語言裡的「洩漏」：程式還參考著已經不需要的物件，GC 因此無法回收那塊記憶體（Microsoft 診斷教學的定義）。

### Event Subscription Leak（事件訂閱沒有解除）
- 定義：訂閱者向生命週期比自己長的事件來源註冊了處理器，卻從不解除。
- 辨識訊號：有 `source.Event += handler`，卻沒有對應的 `-=`；短命物件（視窗、ViewModel、請求範圍的物件）訂閱長命物件（static 事件、單例服務）；記憶體快照中某型別的實例數只增不減，而從 GC root（GC 判斷存活的起點）到它的參考路徑經過事件委派。
- 為何有害：Microsoft 說明，這種寫法建立了從事件來源指向監聽者的強參考；除非明確解除註冊，監聽者的生命週期就被來源綁住，形成記憶體洩漏。已經「死掉」的物件還會繼續收到事件。
- 解法：在對應的生命週期終點解除訂閱（Dispose、Unloaded 等）；用弱事件模式（`WeakEventManager`）；讓來源的生命週期不長於監聽者。
- 何時不算：來源與監聽者同生共死，或來源活得比較短。
- 來源：https://learn.microsoft.com/en-us/dotnet/desktop/wpf/events/weak-event-patterns

### Ever-Growing Static Collection（只加不刪的 static 或單例集合）
- 定義：static 或單例的集合只會加入、從不移除。
- 辨識訊號：static 的 `List`／`Dictionary`／`ConcurrentDictionary` 只有 Add，沒有 Remove；「最近請求」、「已處理 ID」之類的清單沒有上限；`dotnet-counters` 顯示 GC heap 持續成長，兩次 `dotnet-gcdump` 比較出某型別數量持續上升，`gcroot` 指向 static 欄位。
- 為何有害：static 欄位是 GC root，被它參考的物件永遠不會被回收。
- 解法：設上限與淘汰策略（LRU、過期）；改用有上限的快取（見〔Unbounded Cache〕）；不需要長存就別放 static；想「記住，但不阻止回收」就用弱參考（例如 `ConditionalWeakTable`）。
- 何時不算：有上限的查找表，例如啟動時載入的固定代碼表。
- 來源：https://learn.microsoft.com/dotnet/core/diagnostics/debug-memory-leak 〔摘要〕；https://www.site24x7.com/learn/eliminate-net-memory-leaks.html 〔摘要〕；診斷步驟：https://startdebugging.net/2026/07/how-to-diagnose-a-managed-memory-leak-with-dotnet-gcdump-and-dotnet-dump/ 〔摘要〕

### Unbounded Cache（沒有上限的快取）
- 定義：快取既沒有大小上限，也沒有淘汰策略。
- 辨識訊號：`MemoryCache` 沒設 `SizeLimit`；拿 `Dictionary` 當快取；快取鍵直接來自使用者輸入；記憶體隨流量或時間線性成長。
- 為何有害：Microsoft 說明，沒設 `SizeLimit` 的快取會無限成長，ASP.NET Core 也不會依記憶體壓力自動限制；拿使用者輸入當鍵，可能吃掉無法預測的記憶體。CWE-770：配置資源時沒有限制或節流，可被用來造成阻斷服務。
- 解法：設大小上限（`SetSize`／`Size`／`SizeLimit`）與過期時間；讓鍵空間有界；監控快取項數。
- 何時不算：鍵空間天生有界而且小。
- 來源：https://learn.microsoft.com/aspnet/core/performance/caching/memory 〔摘要〕；https://cwe.mitre.org/data/definitions/770.html

### Closure Capture Leak（閉包捕獲造成的洩漏）
- 定義：長壽的委派、lambda 或回呼意外抓住了大物件或 `this`，讓它們跟著活很久。
- 辨識訊號：註冊到長壽事件、Timer、static 集合或快取的 lambda 裡，用到了大型區域變數或 `this` 的成員；ReSharper 出現「implicitly captured closure」警告，表示這個 lambda 可能隱含地抓住了其他 lambda 用到的變數。
- 為何有害：閉包會讓它的詞法環境（被捕獲的變數）一直活著；只要閉包還活著，被捕獲的物件就無法回收。
- 解法：建立閉包前，先取出真正需要的小資料；長壽回呼中避免捕獲 `this`；回呼的註冊要能解除。
- 何時不算：短命、立刻執行完的 lambda，例如 LINQ 查詢內的 lambda。
- 來源：https://resharper-support.jetbrains.com/hc/en-us/community/posts/206704355/comments/205957665 〔摘要〕；https://dev.to/samuel_ochaba_eb9c875fa89/memory-leaks-in-modern-js-a-deep-dive-into-closures-and-garbage-collection-2n72 〔摘要〕

## C2 作業系統資源與配置策略

### Resource Not Released（資源沒有釋放）
- 定義：檔案、連線、socket、handle 等資源在不再需要時沒有釋放。
- 辨識訊號：實作 `IDisposable` 的物件沒用 `using`，也沒呼叫 Dispose；只在成功路徑 Close，例外路徑漏掉；handle 數、連線池使用數只升不降；出現「too many open files」、連線池逾時、socket 耗盡。
- 為何有害：CWE-772：資源在有效生命週期結束後沒有釋放，會耗盡資源、造成阻斷服務。GC 只負責記憶體，回收時機也不確定，不能拿它當作業系統資源的釋放時機。
- 解法：`using`／try-finally／try-with-resources；所有出口（包含錯誤路徑）都要釋放，這也是 CWE 的緩解建議；連線使用連線池。
- 何時不算：刻意長期持有並重用的共享資源（見〔Improper Instantiation〕），但應用程式關閉時要釋放。
- 來源：https://cwe.mitre.org/data/definitions/772.html

### Object Pool Misuse（物件池誤用）
- 定義：在不該用物件池的地方用了池，或使用池的方式錯誤。
- 辨識訊號：池化便宜的小物件；取出的物件沒有歸還，或歸還兩次；歸還後還繼續使用；歸還前沒有重置狀態，下一個使用者看到殘留資料；以為池會限制物件的總配置數量。
- 為何有害：Microsoft 指出，除非初始化成本高，從池取物件通常比較慢；池裡的物件在池本身被釋放前都不會被回收；ObjectPool 限制的是保留數量，而不是配置數量。歸還方式錯誤會造成資料外洩，或兩方同時修改同一個物件。
- 解法：Microsoft 的建議是：先在真實情境收集效能數據，再決定要不要用池；適合池化的物件是建立或初始化昂貴、代表有限資源、被可預測且頻繁使用。歸還一律放在 try/finally；實作重置邏輯（`IResettable` 或 `PooledObjectPolicy`）。
- 何時不算：符合上述條件，而且有量測支持。
- 來源：https://learn.microsoft.com/en-us/aspnet/core/performance/objectpool

### Temporary Large Objects / LOH Fragmentation（暫存大物件／大物件堆碎片）
- 定義：反覆配置短命的大物件。在 .NET 中，85,000 bytes 以上的物件會放進大物件堆（Large Object Heap, LOH）。
- 辨識訊號：每個請求都 new 大陣列或大字串，或呼叫 `MemoryStream.ToArray()`；gen2 GC 次數高，觸發原因是 AllocLarge，而 LOH 存活率很低（Microsoft 用 PerfView 示範的判讀方式）；LOH 大小或虛擬記憶體碎片持續增加。
- 為何有害：Microsoft 說明：大物件的配置成本主要在清零記憶體，清一個 16MB 物件在 2GHz 機器上約需 16ms；LOH 只在 gen2 時回收，暫存的大物件會觸發大量 gen2 GC；LOH 預設只清掃、不壓縮，可能產生碎片；更常見的是暫存大物件讓 GC 頻繁向作業系統取得和歸還記憶體區段，造成虛擬記憶體碎片。
- 解法：Microsoft 建議配置一個大物件池重複使用，而不是一直配置暫存大物件；改用串流處理，不要一次讀進全部；必要時設定 `GCSettings.LargeObjectHeapCompactionMode`。
- 何時不算：長壽的大物件，一次配置、長期使用。其他平台的門檻與機制不同，但「暫存大物件很貴」的原則大致通用〔推論〕。
- 來源：https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/large-object-heap

---

# D. 狀態一致性（State Consistency）

### Duplicated State（同一份資料兩份存法）
- 定義：同一個事實在記憶體裡存了兩份以上，靠程式記得同步。例如清單中的物件之外，又另存一份「目前選取的物件」副本；或資料庫、記憶體快取、UI 各自一份。
- 辨識訊號：更新 A 的地方要「記得」也更新 B；兩份資料的更新散落在不同方法；bug 回報「畫面顯示舊值」「兩處數字對不起來」；同一個值有兩個 setter。
- 為何有害：React 文件指出，同一份資料重複存在多個狀態變數或巢狀物件中時，很難保持同步。並行環境下更糟：兩份資料的更新不是原子的（見〔Composing Independently Atomic Calls〕），別人可能讀到中間狀態。
- 解法：單一真實來源（single source of truth）：只存一份，其他地方只存 ID 或參考，需要時再查。若為了效能必須反正規化（denormalize，刻意存冗餘副本），就把同步集中在一處、一次原子更新，並寫明哪一份才是權威來源。
- 何時不算：刻意的快照，例如表單編輯中的草稿，和原值不同正是預期行為；有明確失效策略的快取（見〔Cache Without Invalidation〕）。
- 來源：https://react.dev/learn/choosing-the-state-structure

### Redundant or Contradictory State（可推導卻另存的狀態／會互相矛盾的狀態）
- 定義：另外存了可以從其他狀態算出來的值，例如 fullName、總數、isEmpty；或用多個旗標描述同一件事，旗標之間可能互相矛盾，例如 isSending 與 isSent 同時為 true。
- 辨識訊號：某欄位的值可以由同物件的其他欄位算出；多個 bool 描述同一個流程的階段；count 欄位與集合長度分開維護。
- 為何有害：React 文件的原則：能從現有狀態算出來的資訊，就不該存成狀態；當幾個狀態可能互相「不同意」時，就留下了出錯空間。
- 解法：改成計算屬性，需要時才算；把多個互斥旗標合併成一個列舉狀態（enum status）。
- 何時不算：計算很昂貴且已有量測，可以快取衍生值，但要有明確的失效點（同〔Cache Without Invalidation〕）。
- 來源：https://react.dev/learn/choosing-the-state-structure

---

# E. 可觀測性（Observability）

### Swallowed Exception（吞掉例外／空 catch）
- 定義：catch 住例外之後什麼都不做，或只做沒有意義的事。
- 辨識訊號：空的 catch 區塊；`catch (Exception) { }`；catch 內只有「ignore」之類的註解；catch 後回傳 null 或預設值，卻沒有任何記錄。靜態分析對應 CWE-1069（Empty Exception Block）。
- 為何有害：CWE-390：偵測到錯誤卻不採取行動，系統會進入非預期的狀態；問題被延後到遠處、以奇怪的方式爆發（Jim Shore 所說的 failing slowly）。
- 解法：只 catch 能處理的特定例外；處理不了就往上拋；真的要忽略，就記錄原因並縮小範圍（具體的例外型別加註解）。
- 何時不算：理由明確、範圍精確的忽略，例如清理階段關閉一個可能已關閉的資源，並附註解；最外層的統一處理器有記錄錯誤。
- 來源：https://cwe.mitre.org/data/definitions/1069.html ；https://cwe.mitre.org/data/definitions/390.html ；https://www.martinfowler.com/ieeeSoftware/failFast.pdf

### Ignored Return Value / Error Code（忽略回傳值或錯誤碼）
- 定義：呼叫一個會回報成功與否或錯誤碼的函式，卻不檢查結果。
- 辨識訊號：`TryXxx` 回傳的 bool 被丟掉，例如 `int.TryParse(s, out v);` 之後直接用 v；`Stream.Read` 回傳的實際讀取位元組數被忽略；不檢查 HTTP 回應狀態碼；不檢查子行程結束碼；不看 `Interlocked.CompareExchange` 的回傳值就假設交換成功。
- 為何有害：CWE-252：沒檢查回傳值，就偵測不到非預期的狀態與錯誤條件，後續操作建立在不成立的前提上。
- 解法：檢查並處理；開啟編譯器或分析器的相關警告（C# 細節見 [03-csharp-dotnet.md](03-csharp-dotnet.md)）；設計 API 時偏好丟例外或回傳 Result 型別，讓「忽略」變得顯眼。
- 何時不算：回傳值確實沒有意義，例如 fluent API 回傳 this；明確丟棄（`_ = …`）並註明原因。
- 來源：https://cwe.mitre.org/data/definitions/252.html

### Silent Fallback / Failing Slowly（靜默降級：默默改用預設值繼續跑）
- 定義：遇到錯誤或缺漏時，默默改用預設值、空集合或舊資料繼續執行，卻不通知任何人。
- 辨識訊號：設定值缺失時回傳寫死的預設值（Shore 的 `maxConnections` 例子）；解析失敗回傳 0；外部服務失敗時回傳空清單；降級路徑沒有 log、metric 或告警。
- 為何有害：Shore 指出，這種「自動繞過問題」的寫法會讓程式出錯後繼續運作，之後以奇怪的方式失敗，堆疊追蹤一路追到死胡同，除錯非常費時。
- 解法：Fail fast：問題發生時立即、明顯地失敗（Shore）。確實需要降級時，降級本身要發出訊號（Warning 等級 log、計數器、告警），讓人知道系統正在降級運作。
- 何時不算：有文件記載的降級策略，而且有可觀測的訊號，例如快取失效時改查來源並計數。
- 來源：https://www.martinfowler.com/ieeeSoftware/failFast.pdf （Jim Shore，IEEE Software 2004）

### Silent Failure in Background Tasks（背景任務靜默失敗）
- 定義：丟到執行緒池或背景執行的任務拋了例外，卻沒有人察覺。
- 辨識訊號：射後不理（fire-and-forget）的呼叫，既不 await 也不保存 Task／Future；Future 從來沒有 `get()`；背景迴圈沒有 try/catch 加 log；某項工作「偶爾沒做」，卻找不到錯誤紀錄。
- 為何有害：CERT TPS03-J 要求池中的任務不得靜默失敗；錯誤直接消失，資料不一致也沒人知道。
- 解法：保存並觀察任務結果；背景迴圈的最外層捕捉例外並記錄；設定全域未處理例外處理器；用 metric 記錄失敗次數。
- 何時不算：成敗真的無所謂的任務，例如盡力而為的遙測，但仍建議計數。
- 來源：CERT TPS03-J「Ensure that tasks executing in a thread pool do not fail silently」：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/rules/thread-pools-tps/

### Excessive Logging / Logging in Hot Path（log 過多／在熱路徑寫 log）
- 定義：log 量多到影響效能，或把有用的訊息淹沒。
- 辨識訊號：熱迴圈或每個請求都寫多條 Info／Debug log；log 訊息在等級過濾之前就已組好（字串插值、`ToString`、序列化物件）；log 檔一天好幾 GB，查事件卻找不到；輪詢迴圈每一輪都寫 log（見〔Are We There Yet?〕）。
- 為何有害：CWE-779：log 太多會讓 log 檔難以處理，妨礙事後復原與鑑識。Microsoft 說明，一般的 logger 擴充方法會對值型別 boxing，並在每次寫 log 時解析訊息樣板，在熱路徑上造成配置與 CPU 成本。Smith 指出過度頻繁地記錄狀態，是較少被注意到的效能問題。
- 解法：依等級分流；熱路徑使用編譯期產生的 logging（.NET 的 `LoggerMessage` 屬性與原始碼產生器，細節見 [03-csharp-dotnet.md](03-csharp-dotnet.md)）；先判斷等級再組訊息；取樣；只記錄狀態變化，不記錄每次檢查；非同步寫 log（Smith）。
- 何時不算：除錯期間暫時開啟、預設關閉的詳細 log。
- 來源：https://cwe.mitre.org/data/definitions/779.html ；https://learn.microsoft.com/dotnet/core/extensions/logging/high-performance-logging 〔摘要〕；https://research.spec.org/icpe_proceedings/2020/proceedings/p173.pdf

### Insufficient Logging（log 過少或缺少關鍵細節）
- 定義：重要事件沒有記錄，或記錄了卻缺少能定位問題的細節。
- 辨識訊號：錯誤 log 只寫「Error occurred」；沒有關聯 ID（correlation ID／request ID，用來串起同一個請求的所有紀錄）；例外 log 沒附堆疊與輸入參數；安全相關事件（登入失敗、權限拒絕）沒有記錄；事後調查時「看了 log 也不知道發生什麼事」。
- 為何有害：CWE-778：安全關鍵事件發生時沒有記錄、或缺少重要細節，就無法偵測惡意行為，也無法在攻擊後做鑑識。
- 解法：記錄「誰、何時、做了什麼、結果如何、關聯 ID」；例外一律附堆疊；使用結構化 log（欄位化）；同時注意不要記錄敏感資料。
- 何時不算：可以由其他訊號（metric、trace）完整重建的純內部細節。
- 來源：https://cwe.mitre.org/data/definitions/778.html

### No Metrics（沒有度量）
- 定義：系統沒有量化的健康指標，只能靠使用者回報或翻 log 才知道出了問題。
- 辨識訊號：沒有延遲、流量、錯誤率、飽和度的數據；沒有 dashboard 或告警；效能問題要重現才看得到；本文件大多數「辨識訊號」都量不到，例如鎖競爭、GC 次數、執行緒數、池使用率、快取命中率、重試次數。
- 為何有害：Google SRE 書提出四個黃金訊號：延遲（latency）、流量（traffic）、錯誤（errors）、飽和度（saturation），並主張針對使用者看得到的症狀告警；沒有這些數據就做不到。也讓〔Premature Optimization〕無法避免，因為沒有數據只能憑感覺優化。
- 解法：至少輸出四個黃金訊號；為本文件提到的資源類訊號加上計數器；針對症狀設告警。
- 何時不算：一次性腳本、原型。
- 來源：https://sre.google/sre-book/monitoring-distributed-systems/

---

# 附錄 A：Smith & Williams 系列效能反模式速查

> 效能反模式（performance antipattern）：常見、看似合理、但會系統性拖垮效能的設計。Smith & Williams 自 2000 年起陸續發表（WOSP 2000；CMG 系列論文〈New Software Performance AntiPatterns: More Ways to Shoot Yourself in the Foot〉等），後續研究者再擴充。下表「一句話」取自引用來源的原文。

| 反模式 | 一句話（原文） | 原文出處 | 本檔對應條目 |
|---|---|---|---|
| Blob / God Class | One class concentrates too much work or data | Aneggi 2026 Table I | Blob |
| Unbalanced Processing | Processing does not use available processors; one slow stage limits throughput | 同上 | Unbalanced Processing |
| Unnecessary Processing | Work is executed although it is not required at that moment or not required at all | 同上 | Unnecessary Processing |
| The Ramp | Processing time grows with system usage or data size | 同上 | The Ramp |
| Sisyphus DB Retrieval | Full queries compute more data than needed（Dugan 等人 2002 定義） | 同上 | Sisyphus Database Retrieval |
| More is Less | Too many processes cause thrashing instead of progress | 同上 | More Is Less |
| Excessive Dynamic Allocation | Too many short-lived objects are created and destroyed | 同上 | Excessive Dynamic Allocation |
| Circuitous Treasure Hunt | Data must be collected from many locations with high lookup cost | 同上 | Circuitous Treasure Hunt |
| One-Lane Bridge | Only one process can continue; others must wait | 同上 | Coarse-Grained Lock |
| Traffic Jam | A temporary issue causes long-lasting request backlogs | 同上 | Traffic Jam |
| Empty Semi Trucks | Occurs when an excessive number of requests is required to perform a task | Cortellessa 等 2023 Table 1 | Empty Semi Trucks |
| Tower of Babel | Occurs when processes use different data formats and they spend too much time in convert them to an internal format | 同上 | Tower of Babel |
| Concurrent Processing Systems | Occurs when processing cannot make use of available processors | 同上 | Unbalanced Processing |
| Pipe and Filter | Occurs when the slowest filter in a "pipe and filter" causes the system to have unacceptable throughput | 同上 | Unbalanced Processing |
| Extensive Processing | Occurs when extensive processing in general impedes overall response time | 同上 | Unbalanced Processing |
| Falling Dominoes | Occurs when one failure causes performance failures in other components | Smith 2020 | Falling Dominoes |
| How Many Times Do I Have to Tell You? | 共用方法被多條路徑重複呼叫，實際只需一次 | Smith 2020 | Repeated Computation |
| Are We There Yet? / Is Everything OK? | 過度頻繁地輪詢事件或檢查平台狀態（Smith 2020 新增） | Smith 2020 | Are We There Yet? |
| Where Was I? | 行程不記得狀態，每次（重新）啟動都從預設狀態開始，得重算狀態（Smith 2020 新增） | Smith 2020 | 未獨立成條 |
| Museum Checkroom | 資源池的元素經同一個先到先服務（FCFS）佇列取用與歸還，最終導致死結；解法：用優先權佇列，讓歸還者優先（Bondi 提出） | Smith 2020 | 未獨立成條（並行死結類） |
| Spin Wait | 實作層級的忙等（Boroday 等人 2005） | SPEC RG 2015 | Busy Waiting |

補充：SPEC RG 報告指出，這些反模式的抽象層次不同：有的是架構層（Blob），有的是實作層（Spin Wait），有的是部署層（Unbalanced Processing）；有的只描述症狀（The Ramp），有的描述根因（Sisyphus）；有的是結構型（Blob），有的是行為型（Empty Semi Trucks）。偵測方法要依類型挑選。Smith 也強調，偵測到反模式不等於一定有效能問題，例如使用量很低的 One-Lane Bridge 就無害。

# 附錄 B：Azure 效能反模式對照（簡表，詳見 [04-client-server.md](04-client-server.md) 附錄 1）

| Azure 反模式 | 官方一句話 | 本檔對應 |
|---|---|---|
| Busy Database | Offloading too much processing to a data store. | 無直接對應（近似資料層的 Blob） |
| Busy Front End | Moving resource-intensive tasks onto background threads. | Unbalanced Processing、More Is Less |
| Chatty I/O | Continually sending many small network requests. | Empty Semi Trucks、Circuitous Treasure Hunt |
| Extraneous Fetching | Retrieving more data than is needed, resulting in unnecessary I/O. | Sisyphus Database Retrieval |
| Improper Instantiation | Repeatedly creating and destroying objects that are designed to be shared and reused. | Improper Instantiation |
| Monolithic Persistence | Using the same data store for data with very different usage patterns. | 無（架構層） |
| No Caching | Failing to cache data. | Repeated Computation 的反面；與 Over-Caching 是兩個極端 |
| Noisy Neighbor | A single tenant uses a disproportionate amount of the resources. | 無（多租戶） |
| Retry Storm | Retrying failed requests to a server too often. | Falling Dominoes |
| Synchronous I/O | Blocking the calling thread while I/O completes. | Blocking While Holding a Lock、Interdependent Tasks in a Bounded Pool（[03-csharp-dotnet.md](03-csharp-dotnet.md) 詳述） |

來源：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/

# 附錄 C：能源壞味道（energy smells）12 類

Mehditabar、Rajput、Sharma（2026）〈Watts This Smell〉：系統性回顧 60 篇論文，歸納出 12 種主要能源壞味道與 65 種根因，並以 21,000 組以上功能相同的 Python 程式對做能耗量測驗證。

| 代號 | 名稱 | 原文定義（節錄） | 本檔相關條目 |
|---|---|---|---|
| C1 | Redundant Computation | 結果從未被使用，或重做已做過的計算 | Unnecessary Processing、Repeated Computation |
| C2 | Unnecessary Call Overhead | 函式呼叫、委派、動態分派的成本沒有對應的效益 | — |
| C3 | Inefficient Iteration Patterns | 每圈做太多、圈數太多、或沒有提早結束 | Repeated Computation |
| C4 | Inefficient Control Flow | 多餘的檢查、不佳的判斷順序 | — |
| C5 | Suboptimal Data Structures | 容器與存取模式不合 | Hidden Quadratic |
| C6 | Unnecessary Memory Usage | 配置、複製、保留超過需要的記憶體 | Unnecessary Deep Copy、Excessive Dynamic Allocation |
| C7 | Suboptimal Algorithmic | 演算法複雜度高於問題所需 | Hidden Quadratic、The Ramp |
| C8 | Missing Reuse | 昂貴的計算結果沒有儲存重用 | Repeated Computation |
| C9 | Inefficient External Data Access | 與資料庫、檔案系統、API 的互動沒效率 | B3 全部 |
| C10 | Underused Language Primitives | 沒用內建的最佳化函式或結構 | — |
| C11 | Inefficient Concurrency Management | 過度鎖競爭、序列瓶頸、錯失平行機會 | Coarse-Grained Lock、Over-Synchronization |
| C12 | Poor Hardware Locality | 快取未命中、分支預測失敗、記憶體存取模式差 | — |

研究發現：71% 的樣本同時有多種壞味道；記憶體相關的壞味道（C5、C6）每次修復省下的能耗中位數最高；功耗的差異證明「能源最佳化不能化約為效能最佳化」。另一篇研究（Aneggi 等人 2026）則發現，效能反模式對能耗的影響並不一致：The Ramp、God Class、Traffic Jam 會同時拉高回應時間與功耗；Excessive Dynamic Allocation 的 CPU 能耗最高；Unnecessary Processing 的 DRAM 能耗最高；部分反模式因 CPU 已滿載，變慢後只是「跑更久」，功率本身沒有上升。

來源：https://arxiv.org/abs/2604.04809 ；https://arxiv.org/abs/2602.12079

# 附錄 D：研究數據（審查並行程式碼時的取捨依據）

**Lu、Park、Seo、Zhou（ASPLOS 2008）〈Learning from Mistakes〉**：分析 MySQL、Apache、Mozilla、OpenOffice 的 105 個真實並行 bug。
- 97% 的非死結 bug 屬於「原子性違反」或「順序違反」兩種樣式 → 審查時優先找〔Check-Then-Act〕、〔Non-atomic Read-Modify-Write〕、〔Order Violation〕。
- 約三分之一的非死結 bug 是順序違反，不容易用鎖表達。
- 34% 的非死結 bug 涉及多個變數（66% 只涉及一個變數）→ 多變數一致性要另外檢查（〔Invariant Split Across Locks〕、〔Composing Independently Atomic Calls〕）。
- 96% 的 bug 只要強制兩條執行緒間的某個先後順序就必定發生；105 個中有 101 個只涉及兩條以內的執行緒 → 審查時「兩條執行緒、兩個存取點」的推演就能抓到絕大多數問題。
- 92% 的 bug 只要控制最多 4 個記憶體存取的順序就能穩定觸發。
- 97% 的死結 bug 是兩條執行緒循環等待最多兩個資源 → 重點檢查成對的巢狀鎖（〔Inconsistent Lock Ordering〕）。
- 73% 的非死結 bug 不是單純加鎖或改鎖修好的，而且很多修補第一次就修錯 → 不要把「加個 lock」當萬用解。
- 來源：https://www.cs.columbia.edu/~junfeng/08fa-e6998/sched/readings/concurrency-bugs.pdf

**Farchi、Nir、Ur（IPDPS 2003）〈Concurrent Bug Patterns and How to Test Them〉**〔摘要〕：把並行 bug 分成「以為受保護的程式碼」（Code Assumed to Be Protected）、「以為不會發生的交錯」（Interleavings Assumed Never to Occur）、「以為不會阻塞」（Blocking or Dead Thread）等類，並列出「遺失通知」（Losing a Notify）等具體樣式。來源：https://research.ibm.com/publications/concurrent-bug-patterns-and-how-to-test-them

**Tamburri 等人（2023）〈Architecture Smells vs. Concurrency Bugs〉**〔摘要〕：在 5 個大型資料密集系統、125 個版本上發現，架構壞味道整體上與並行 bug 不相關，只有在「天生分散式」而且「發版很頻繁」的專案中才有關聯 → 不要拿架構層的壞味道當並行 bug 的替代指標，要看程式碼層的形狀。來源：https://arxiv.org/abs/2303.17862

# 附錄 E：來源清單與查證狀態

**讀過原文（頁面或 PDF 全文）**
- Microsoft, Managed threading best practices：https://learn.microsoft.com/en-us/dotnet/standard/threading/managed-threading-best-practices
- Microsoft, volatile（C# 參考）：https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/keywords/volatile
- Microsoft, Large object heap：https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/large-object-heap
- Microsoft, ObjectPool：https://learn.microsoft.com/en-us/aspnet/core/performance/objectpool
- Microsoft, Weak event patterns：https://learn.microsoft.com/en-us/dotnet/desktop/wpf/events/weak-event-patterns
- Microsoft Azure, Performance antipatterns 目錄：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/
- Microsoft Azure, Improper Instantiation：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/improper-instantiation/
- Microsoft Azure, Chatty I/O：https://learn.microsoft.com/en-us/azure/architecture/antipatterns/chatty-io/
- SEI CERT Oracle Java 標準：LCK07-J、LCK09-J、VNA02-J、VNA03-J、TPS00-J 讀過內文；LCK00/01/08/10/11-J、THI02/03/05-J、TSM01/02/03-J、TPS01/03/04-J 只核對過規則標題。根目錄：https://cmu-sei.github.io/secure-coding-standards/sei-cert-oracle-coding-standard-for-java/
- Pugh 等人, The "Double-Checked Locking is Broken" Declaration：https://www.cs.umd.edu/~pugh/java/memoryModel/DoubleCheckedLocking.html
- Goetz（2001）, Avoid synchronization deadlocks：https://www.infoworld.com/article/2075692/avoid-synchronization-deadlocks.html
- Lu 等人（2008）, Learning from Mistakes：https://www.cs.columbia.edu/~junfeng/08fa-e6998/sched/readings/concurrency-bugs.pdf
- Smith（ICPE 2020）, Software Performance Antipatterns in Cyber-Physical Systems：https://research.spec.org/icpe_proceedings/2020/proceedings/p173.pdf （DOI 10.1145/3358960.3379138）
- Aneggi、Stoico、Janes（2026）, Performance Antipatterns: Angel or Devil for Power Consumption?：https://arxiv.org/abs/2602.12079
- Cortellessa 等人, Many-Objective Optimization of Non-Functional Attributes based on Refactoring of Software Models（Table 1）：https://arxiv.org/abs/2301.09531
- Cortellessa 等人, A model-driven approach to broaden the detection of software performance antipatterns at runtime：https://arxiv.org/abs/1404.0851
- SPEC RG（2015）, Performance-oriented DevOps: A Research Agenda（§4.3.1）：https://arxiv.org/abs/1508.04752
- Mehditabar、Rajput、Sharma（2026）, Watts This Smell：https://arxiv.org/abs/2604.04809
- Accidentally Quadratic：https://accidentallyquadratic.tumblr.com/
- Knuth 引文：https://probablydance.com/2025/06/19/revisiting-knuths-premature-optimization-paper/
- Fowler, TwoHardThings：https://martinfowler.com/bliki/TwoHardThings.html
- Jim Shore（IEEE Software 2004）, Fail Fast：https://www.martinfowler.com/ieeeSoftware/failFast.pdf
- React, Choosing the State Structure：https://react.dev/learn/choosing-the-state-structure
- Google SRE Book, Monitoring Distributed Systems：https://sre.google/sre-book/monitoring-distributed-systems/
- CWE-252、390、770、772、778、779、1069：https://cwe.mitre.org/data/definitions/<編號>.html

**只經搜尋摘要確認〔摘要〕**
- JCIP 引文（三種修法、不變量同鎖規則、第 11 章減少鎖競爭）：tufts／UMD 講義（UMD 第 11 章 PDF 直接抓取時回 403）
- Bloch〈Effective Java〉的 alien method／open call 說法
- Farchi 等人 2003；Tamburri 等人 2023
- Microsoft：Retry Storm、記憶體快取（SizeLimit）、高效能 logging、Lazy initialization、Debug a memory leak
- Busy waiting（Wikipedia、xygeni）、Thread leak（morling.dev、gceasy）、static 集合洩漏（site24x7、startdebugging）、閉包捕獲（JetBrains、dev.to）
- Trubiani 等人的反模式重構解法（給短任務較高優先權）

**未查證／推論**
- 〔Over-Caching〕整條：找不到專門定義此味道的權威來源，由物件池與快取文件推論而來。
- 〔Broken Double-Checked Locking〕中「.NET 上 DCL 是否安全」：未查證，條目只建議一律改用 `Lazy<T>`。
- 〔Temporary Large Objects〕中「其他平台原則大致通用」：推論。
- 附錄 A 中 Smith & Williams 各篇論文的確切年份與原始定義：原論文 PDF 無法取得（UW 課程連結需登入），一句話定義改用後續論文的轉述原文。

# C# Server 全面異常危險狀態清單（通用知識庫）

> 目標：窮舉 C# 打造的 Server 程式碼中，所有已知可能引發異常的危險狀態與原因。
> 來源：公開文獻、.NET Runtime Issues、Stack Overflow、CVE、微軟官方文件、遊戲伺服器實戰經驗。

---

## 目錄

1. [執行緒與併發](#1-執行緒與併發-threading--concurrency)
2. [集合操作](#2-集合操作-collections)
3. [Async/Await 陷阱](#3-asyncawait-陷阱)
4. [記憶體與 GC](#4-記憶體與-gc)
5. [網路與 Socket](#5-網路與-socket)
6. [資料庫](#6-資料庫)
7. [序列化與反序列化](#7-序列化與反序列化)
8. [Null 參照](#8-null-參照)
9. [型別轉換與數值溢位](#9-型別轉換與數值溢位)
10. [資源管理 (IDisposable)](#10-資源管理-idisposable)
11. [字串處理](#11-字串處理)
12. [日期與時間](#12-日期與時間)
13. [檔案與 I/O](#13-檔案與-io)
14. [定時器與排程](#14-定時器與排程)
15. [反射與動態程式碼](#15-反射與動態程式碼)
16. [設定與環境](#16-設定與環境)
17. [安全性](#17-安全性)
18. [CLR / Runtime 層級](#18-clr--runtime-層級)
19. [Interop 與 Native](#19-interop-與-native)
20. [.NET Core 特有問題](#20-net-core-特有問題)
21. [邏輯層級危險](#21-邏輯層級危險)
22. [Log 與診斷的反噬](#22-log-與診斷的反噬)

---

## 1. 執行緒與併發 (Threading & Concurrency)

### 1.1 資料競爭 (Data Race)
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 1.1.1 | 多執行緒同時讀寫同一個 `Dictionary<K,V>` | 無鎖保護的共享字典 | `IndexOutOfRangeException`、`NullReferenceException`、內部桶陣列損壞導致**無限迴圈 CPU 100%** (已知 .NET bug, 非常難查) |
| 1.1.2 | 多執行緒同時讀寫 `List<T>` | 無鎖保護的共享列表 | `ArgumentOutOfRangeException`、`IndexOutOfRangeException`、內部 `_items` 陣列損壞 |
| 1.1.3 | 多執行緒同時讀寫 `HashSet<T>` | 同上 | 同 Dictionary，內部桶損壞 |
| 1.1.4 | `ConcurrentDictionary` 的複合操作不原子 | 先 `ContainsKey` 再 `Add`，兩步之間被插入 | `ArgumentException` (key already exists) 或邏輯錯誤 |
| 1.1.5 | 對 `bool` / `int` 等基本型別的非 Volatile 讀取 | 編譯器/CPU 快取導致讀到過期值 | 無異常但行為錯誤（如循環不終止、狀態判斷錯） |
| 1.1.6 | `i++` 非原子操作 | 多執行緒遞增計數器未用 `Interlocked` | 計數遺失（Lost Update），統計數據不準 |
| 1.1.7 | 64-bit 數值在 32-bit 平台上 torn read | `long` / `double` 在 x86 上非原子讀寫 | 讀到半新半舊的值（撕裂讀取），無異常但數據損壞 |

### 1.2 死鎖 (Deadlock)
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 1.2.1 | 經典 AB-BA 死鎖 | 兩個執行緒以不同順序取得兩把鎖 | 永久掛起，Server 無回應 |
| 1.2.2 | `lock` 內呼叫外部方法 | 外部方法內部也嘗試取鎖 | 死鎖或不可預期的重入 |
| 1.2.3 | `lock` 內做 I/O（DB/Network/File） | I/O 延遲期間持有鎖，其他執行緒全部等待 | 效能崩潰，看似死鎖（隱性飢餓） |
| 1.2.4 | `Monitor.Enter` 但異常路徑漏了 `Monitor.Exit` | 異常跳過 finally（極端情況） | 鎖永遠不釋放 → 後續存取全掛 |
| 1.2.5 | `ReaderWriterLockSlim` 遞迴策略設錯 | 預設 `NoRecursion`，同執行緒二次進入 | `LockRecursionException` |
| 1.2.6 | `SemaphoreSlim.WaitAsync` + 同步 `.Wait()` 混用 | 在 sync context 上用 `.Result` 等待 async lock | 死鎖（SynchronizationContext 佔滿） |

### 1.3 執行緒安全的錯覺
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 1.3.1 | 「只讀不寫所以安全」的假設 | 初始化後有極低頻率的寫入路徑被忽略 | 在壓力下才出現的 race condition |
| 1.3.2 | `Lazy<T>` 的 `LazyThreadSafetyMode` 選錯 | 用了 `None` 在多執行緒環境 | 多次初始化、或拿到半初始化的物件 |
| 1.3.3 | 靜態建構子 (static ctor) 死鎖 | 兩個類別的靜態建構子互相依賴 | 永久掛起，CLR 級別無法恢復 |
| 1.3.4 | `ThreadStatic` 在 async 中失效 | async 方法 resume 時可能在不同 thread | 讀到別的執行緒的資料或 null |
| 1.3.5 | `volatile` 不保證原子性 | 對 `volatile long` 仍有 torn read（32-bit） | 數據損壞 |

### 1.4 ThreadPool 飢餓
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 1.4.1 | 阻塞式呼叫佔滿 ThreadPool | 大量 `.Result` / `.Wait()` / `Thread.Sleep` | 新請求無法被處理，Server 看似活著但不回應 |
| 1.4.2 | `Timer` callback 排不上 | ThreadPool 滿載 | 定時器延遲數秒到數分鐘才觸發 |
| 1.4.3 | `Task.Run` 爆量 | 每個請求都 `Task.Run` 而不用 async I/O | ThreadPool 成長追不上，排隊延遲暴增 |

---

## 2. 集合操作 (Collections)

### 2.1 迭代中修改
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 2.1.1 | `foreach` 中 `Add` / `Remove` | 同一集合在迭代中被修改 | `InvalidOperationException: Collection was modified` |
| 2.1.2 | 多執行緒：A 迭代、B 修改 | 無鎖保護 | 同上，但不穩定復現——壓力大才爆 |
| 2.1.3 | `for (int i=0; i<list.Count; i++)` 中 `RemoveAt` | 索引偏移 | `ArgumentOutOfRangeException` 或跳過元素 |
| 2.1.4 | LINQ `.ToList()` 中途原集合被改 | LINQ 是延遲求值 | 同 2.1.1 |

### 2.2 鍵值查找
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 2.2.1 | `dict[key]` 而 key 不存在 | 沒用 `TryGetValue` | `KeyNotFoundException` |
| 2.2.2 | 自訂 `GetHashCode` 不穩定 | 可變物件當 key，hash 改變後找不回 | 邏輯錯誤（永遠找不到已存在的 key），記憶體洩漏 |
| 2.2.3 | `GetHashCode` / `Equals` 不一致 | 兩個 Equal 的物件 hash 不同 | Dictionary 行為未定義 |
| 2.2.4 | `null` 作為 `Dictionary` key | 值型別 key 不可能，引用型別 key 可能傳 null | `ArgumentNullException` |

### 2.3 容量與記憶體
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 2.3.1 | `List<T>` 無限增長 | 只 Add 不 Remove（洩漏模式） | `OutOfMemoryException` |
| 2.3.2 | 巨大 `Dictionary` resize | 元素數超過桶數量觸發 rehash | 單次 rehash 花費數百毫秒，遊戲卡頓 |
| 2.3.3 | `Array.Resize` 在大陣列上 | 需要連續記憶體區塊 | `OutOfMemoryException`（碎片化時即使總量夠也分配失敗） |
| 2.3.4 | `Queue<T>` / `Stack<T>` 不會自動縮容 | 高峰期撐大後，低峰期記憶體不回收 | 持續高記憶體佔用 |

---

## 3. Async/Await 陷阱

### 3.1 死鎖模式
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 3.1.1 | `.Result` / `.Wait()` 在有 SyncContext 的環境 | UI thread 或 ASP.NET 的 SyncContext 被佔住 | 永久死鎖 |
| 3.1.2 | `ConfigureAwait(false)` 漏加 | Library 程式碼 capture 了不需要的 SyncContext | 隱性死鎖風險 |
| 3.1.3 | async void 方法 | 除了事件處理器以外用 `async void` | 異常無法被 catch，直接崩潰 process |

### 3.2 例外處理
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 3.2.1 | `Task` 異常未觀察 (Unobserved) | fire-and-forget 沒 await 也沒 ContinueWith | .NET 4.0 會崩 process；4.5+ 預設吞掉但邏輯錯誤被靜默隱藏 |
| 3.2.2 | `AggregateException` 未展開 | `.Wait()` 包裹了 `AggregateException` | catch 的 exception type 不匹配，異常逃逸 |
| 3.2.3 | `Task.WhenAll` 只報第一個異常 | 多個 task 都失敗 | 後續異常被吞掉，除非檢查 `Task.Exception` |

### 3.3 併發控制
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 3.3.1 | `async` 方法內無 concurrent guard | 同一玩家同時發兩個請求 | 重入導致資料不一致 |
| 3.3.2 | `CancellationToken` 未傳遞 | 長時間操作無法取消 | Server 關閉時 graceful shutdown 超時 |
| 3.3.3 | `SemaphoreSlim` 在 dispose 後使用 | 物件生命週期管理不當 | `ObjectDisposedException` |
| 3.3.4 | `async` lambda capture 可變變數 | 迴圈中的 `async` lambda 共享迴圈變數 | 全部 lambda 看到最終值 |

### 3.4 Task 生命週期
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 3.4.1 | `TaskCompletionSource` 未完成 | 忘記在所有路徑 SetResult/SetException | await 的人永遠掛著 |
| 3.4.2 | `TaskCompletionSource` 多次 SetResult | 同一 TCS 被完成兩次 | `InvalidOperationException` |
| 3.4.3 | `Task.Delay(-1)` 但沒 CancellationToken | 無限等待且無法取消 | 記憶體洩漏（Timer 物件永遠存活） |

---

## 4. 記憶體與 GC

### 4.1 記憶體洩漏
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 4.1.1 | 事件訂閱未取消 (`+=` 無對應 `-=`) | 訂閱者被事件源引用，無法被 GC | 記憶體持續增長 → OOM |
| 4.1.2 | 靜態集合持有物件引用 | `static Dictionary` / `static List` 只加不刪 | 同上 |
| 4.1.3 | Closure 捕獲大物件 | Lambda / delegate 隱式引用了不需要的大物件 | 大物件生命週期被意外延長 |
| 4.1.4 | `Timer` 未 Dispose | `System.Threading.Timer` 的 callback delegate 引用物件 | 物件和 Timer 都無法回收 |
| 4.1.5 | `CancellationTokenSource` 未 Dispose | 內部 Timer 和 callback 鏈不釋放 | 每次請求洩漏一小塊，累積成大問題 |
| 4.1.6 | `StringBuilder` / `MemoryStream` 大量暫存不回收 | 池化對象的內部 buffer 只增不縮 | 記憶體碎片 + 高水位不降 |
| 4.1.7 | WeakReference 的 Target 已被回收但 Entry 仍在集合中 | 沒有定期清理失效的 WeakReference | 集合本身持續膨脹 |

### 4.2 GC 壓力
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 4.2.1 | 高頻分配短命物件 | 每個封包都 `new byte[]`、每次拼字串都 `new string` | Gen0 GC 頻繁，STW (Stop-The-World) 卡頓 |
| 4.2.2 | 大物件堆 (LOH) 碎片化 | 分配 > 85,000 bytes 的 `byte[]` | LOH 不壓縮(compact)，可用記憶體充足但分配失敗 → OOM |
| 4.2.3 | Pinned 物件過多 | 大量 `GCHandle.Alloc(obj, Pinned)` 或 `fixed` | GC 無法移動物件，堆碎片化加劇 |
| 4.2.4 | Gen2 GC 頻繁觸發 | 大量長壽命物件 + 持續分配 | 每次 Gen2 GC 暫停數十到數百毫秒 |
| 4.2.5 | `Finalize` 佇列堆積 | 含有 Finalizer 的物件大量產生 | Finalizer thread 追不上 → 記憶體暴漲 |

### 4.3 Stack 相關
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 4.3.1 | 無限遞迴 | 遞迴終止條件錯誤 | `StackOverflowException`（**不可 catch，直接殺 process**） |
| 4.3.2 | 深度遞迴 + 大量 local 變數 | 每層 frame 佔用大量 stack | 同上 |
| 4.3.3 | `stackalloc` 大陣列 | `stackalloc byte[1000000]` | 同上 |

---

## 5. 網路與 Socket

### 5.1 TCP 連線管理
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 5.1.1 | 對已關閉的 Socket 操作 | 未檢查連線狀態就 Send/Receive | `ObjectDisposedException`、`SocketException` |
| 5.1.2 | `Send` 返回值未檢查 | `Send` 不保證一次送完所有 bytes | 對端收到不完整封包 → 解析崩潰 |
| 5.1.3 | `Receive` 返回 0 未處理 | 返回 0 表示對端優雅關閉 | 無限迴圈讀取 0 bytes（CPU 100%） |
| 5.1.4 | 半開連線 (Half-Open) | 網路中斷但未發 FIN/RST | 連線看似活著但永遠不回資料，佔用資源不釋放 |
| 5.1.5 | `TIME_WAIT` 耗盡 | Server 頻繁主動關閉連線 | Port 耗盡，新連線失敗 `SocketException: Address already in use` |
| 5.1.6 | `SocketAsyncEventArgs` 重複使用未 reset | `SetBuffer` 後 args 仍引用舊 buffer | 記憶體洩漏或資料錯亂 |
| 5.1.7 | Nagle 算法 + Delayed ACK 組合 | 小封包被延遲 40ms~200ms | 遊戲手感延遲（非異常但致命） |
| 5.1.8 | Backlog 滿了 | `Socket.Listen(backlog)` 的 backlog 設太小 | 新連線被靜默丟棄（Linux）或 RST（Windows） |

### 5.2 粘包與拆包
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 5.2.1 | TCP 粘包未處理 | 多個封包在一次 Receive 中收到 | 封包邊界錯亂，解析出垃圾資料 |
| 5.2.2 | 封包長度欄位被惡意篡改 | 攻擊者發送 `length = 2GB` | 分配巨大 buffer → `OutOfMemoryException` |
| 5.2.3 | 拆包邏輯 off-by-one | 長度計算差一個 byte | 後續所有封包全部解析失敗 |
| 5.2.4 | Endianness 不匹配 | Server 和 Client 的位元組序不一致 | 長度欄位讀成天文數字 |

### 5.3 SSL/TLS
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 5.3.1 | 憑證過期未更新 | SSL 憑證到期 | `AuthenticationException`，所有新連線失敗 |
| 5.3.2 | TLS 交握超時 | Client 只建 TCP 不做 TLS handshake（慢速攻擊） | 連線槽被耗盡 |
| 5.3.3 | `SslStream` Dispose 順序 | 先 Dispose 底層 Socket 再 Dispose SslStream | `ObjectDisposedException` |

### 5.4 DNS 問題
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 5.4.1 | DNS 查詢阻塞 | `Dns.GetHostEntry` 是同步的 | DNS 超時（預設 5s~30s），期間執行緒被卡住 |
| 5.4.2 | DNS 快取 TTL 過期後解析失敗 | DNS 服務不可用 | 重連失敗（即使 IP 沒變，因為是透過域名連的） |
| 5.4.3 | DNS 結果快取不更新 | `ServicePointManager` 舊行為 | IP 切換後仍連舊位址 |

---

## 6. 資料庫

### 6.1 連線管理
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 6.1.1 | 連線池耗盡 | 連線未歸還（漏 Dispose）或並發量超過 Max Pool Size | `MySqlException: Too many connections` / `TimeoutException` |
| 6.1.2 | 連線在 idle 後失效 | MySQL `wait_timeout` 到期，pool 中的連線被 server 斷開 | 下次使用時 `MySqlException: Connection lost` |
| 6.1.3 | 網路瞬斷導致連線壞死 | TCP RST 但 client 不知 | 第一次操作才報錯，且 pool 中可能有多條壞連線 |
| 6.1.4 | 連線字串含密碼，日誌洩漏 | 異常訊息包含連線字串 | 密碼洩漏到 log 檔 |

### 6.2 查詢問題
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 6.2.1 | SQL Injection | 字串拼接 SQL 而非參數化 | 資料洩漏或刪庫（`DROP TABLE`） |
| 6.2.2 | 查詢超時 | 大表無索引的 `SELECT` / 鎖等待 | `MySqlException: Timeout` |
| 6.2.3 | 鬼讀/不可重複讀 | 交易隔離層級不當 | 資料不一致（如金幣被多扣） |
| 6.2.4 | N+1 問題 | 迴圈內逐筆查詢 | 效能崩潰（10,000 名玩家 = 10,000 次 DB round-trip） |
| 6.2.5 | `BLOB` 大物件讀取 | 一次讀取 MB 級的 BLOB | 記憶體暴漲、GC 壓力 |
| 6.2.6 | 死鎖 (DB level) | 兩個 transaction 互相等對方的 row lock | `MySqlException: Deadlock found` |

### 6.3 事務問題
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 6.3.1 | Transaction 未 Commit 也未 Rollback | 異常路徑漏了 finally | 連線歸還時隱式 rollback，但可能鎖未釋放 |
| 6.3.2 | 長時間 Transaction | Transaction 內做耗時操作（如呼叫外部 API） | 行鎖持續時間過長，其他操作全部等待 |
| 6.3.3 | 分散式事務不一致 | 跨 Server 操作（如轉帳：A 伺服器扣錢，B 伺服器加錢） | A 成功 B 失敗 → 金幣消失 |
| 6.3.4 | Auto-increment gap | Transaction rollback 後，自增 ID 出現缺口 | 非異常但可能影響業務邏輯（如果依賴連續 ID） |

### 6.4 MySQL X Protocol 特有
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 6.4.1 | X Protocol 序列化開銷大 | Protobuf over X Protocol 的雙層序列化 | 效能比傳統 MySQL Protocol 差 |
| 6.4.2 | `Collection.Find()` CRUD API 效能差 | 文件模式(NoSQL)操作大量資料 | 比原生 SQL 慢數倍 |
| 6.4.3 | Session 數量超過 `mysqlx_max_connections` | 配置不足 | 新 Session 建立失敗 |

---

## 7. 序列化與反序列化

### 7.1 Protobuf 相關
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 7.1.1 | Proto 版本不匹配 | Client 和 Server 的 .proto 定義不同步 | 欄位錯位 → 資料損壞（**非常隱蔽，不一定拋異常**） |
| 7.1.2 | Unknown fields 導致大小暴增 | 舊版本保留新版本加的欄位 | 每次序列化都帶著未知欄位 → 封包膨脹 |
| 7.1.3 | 遞迴 Message | A 引用 B，B 引用 A | 序列化時 `StackOverflowException` |
| 7.1.4 | 超大 Message | 單一 Message 超過 `CodedInputStream.DefaultSizeLimit` (64MB) | `InvalidProtocolBufferException` |
| 7.1.5 | 惡意構造的 varint | 變長整數永遠不終止 | 解析迴圈不停 / 超時 |
| 7.1.6 | `repeated` 欄位填充攻擊 | 攻擊者發送含百萬元素的 repeated field | OOM |
| 7.1.7 | `oneof` 欄位類型錯誤 | 設了一個 oneof case 但讀另一個 | 讀到 default 值，邏輯錯但無異常 |
| 7.1.8 | 預設值不傳輸 | Protobuf 3 的 `0` / `""` / `false` 不會序列化到 wire | 無法區分「有設值=0」和「沒設值」→ 遊戲邏輯 bug |

### 7.2 通用序列化
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 7.2.1 | `BinaryFormatter` 反序列化不受信資料 | RCE 漏洞（CVE-2020-1147 等） | **遠端程式碼執行** |
| 7.2.2 | JSON 解析巨大數字 | `JsonSerializer` 處理超出 double 精度的數字 | 精度遺失或 `JsonException` |
| 7.2.3 | 循環引用序列化 | 物件圖有環 | `JsonException` 或無限遞迴 |
| 7.2.4 | 反序列化建構子副作用 | 型別的建構子做了不該做的事 | 反序列化觸發資料庫寫入等意外操作 |
| 7.2.5 | Buffer 邊界未檢查 | 手動讀寫 byte[] 時索引計算錯誤 | `IndexOutOfRangeException` 或讀到錯誤資料 |

---

## 8. Null 參照

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 8.1 | 字典查找結果未判 null | `dict.TryGetValue` 的 out 值是 null（引用型別） | `NullReferenceException` |
| 8.2 | 事件觸發未判 null | `MyEvent.Invoke(...)` 但沒人訂閱 | `NullReferenceException`（應用 `MyEvent?.Invoke()`） |
| 8.3 | LINQ `FirstOrDefault` 結果未判 null | 找不到元素時返回 null | `NullReferenceException` |
| 8.4 | 多層屬性鏈 | `player.Guild.Leader.Name` 中途某層是 null | `NullReferenceException` |
| 8.5 | `as` 轉型失敗 | `obj as MyType` 返回 null | 後續使用未判 null |
| 8.6 | `Nullable<T>.Value` 未先判 HasValue | 直接存取 `.Value` | `InvalidOperationException` |
| 8.7 | async 方法返回 null Task | `return null` 而非 `Task.CompletedTask` | await null → `NullReferenceException` |
| 8.8 | 物件建構後半初始化 | 建構子完成但 `Initialize()` 還沒呼叫 | 成員仍是 null |
| 8.9 | Dispose 後存取 | 物件已 Dispose，成員被設 null | `NullReferenceException` 或 `ObjectDisposedException` |

---

## 9. 型別轉換與數值溢位

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 9.1 | `int` 溢位 | 大數值相乘未用 `checked` | 默默 wrap around（如傷害計算變負數） |
| 9.2 | `(int)longValue` 截斷 | long 值超過 int.MaxValue | 靜默截斷（高位丟失），數值驟變 |
| 9.3 | `float` / `double` 精度遺失 | 金幣用浮點計算 | 0.1 + 0.2 ≠ 0.3，長期累積差異 |
| 9.4 | `InvalidCastException` | `(MyClass)obj` 失敗 | 硬轉型異常 |
| 9.5 | `Convert.ToInt32(string)` | 非數字字串 | `FormatException` |
| 9.6 | `Enum` 超出定義範圍 | `(MyEnum)999` 不會拋異常 | 不在定義內的 enum 值四處傳播，switch 走 default |
| 9.7 | 除以零 | `int / 0` | `DivideByZeroException`（`double / 0.0` = `Infinity`，不拋異常但可能污染後續計算） |
| 9.8 | `checked` 溢位 | 在 `checked` 區塊內溢位 | `OverflowException` |
| 9.9 | `DateTime.Ticks` 轉 `int` | Ticks 是 long，遠超 int 範圍 | 截斷 |
| 9.10 | 位移運算超出範圍 | `1 << 32` 在 int 上 | C# 會 mod 32，結果等於 `1 << 0`，非預期 |

---

## 10. 資源管理 (IDisposable)

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 10.1 | `using` 缺失 | 手動 `new` 了 Stream/Connection 但沒 using | 資源洩漏（FD/Handle/Connection） |
| 10.2 | `Dispose` 內拋異常 | Dispose 方法不該拋異常但拋了 | 原始異常被遮蔽（`using` 的 finally 異常取代 try 異常） |
| 10.3 | 雙重 Dispose | 同一物件 Dispose 兩次 | 設計良好的 class 應容忍，但非所有實作都做到 |
| 10.4 | `HttpClient` 頻繁 new/dispose | 每次請求都 new | `SocketException` (TIME_WAIT 端口耗盡) |
| 10.5 | `Stream` dispose 順序 | `StreamWriter` dispose 時 flush 底層 stream；如果底層已關 | 異常或資料遺失 |
| 10.6 | `CancellationTokenSource` 未 dispose | 內部 Timer 和 registration 不釋放 | 記憶體洩漏 |
| 10.7 | `GCHandle.Free()` 未呼叫 | Pinned/Normal handle 不釋放 | GC 無法回收對應物件 |

---

## 11. 字串處理

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 11.1 | 迴圈內 `+= string` | 每次產生新字串（O(n²) 記憶體分配） | GC 壓力暴增，高頻路徑卡頓 |
| 11.2 | `string.Format` 參數數量不匹配 | 格式字串有 `{2}` 但只給兩個參數 | `FormatException` |
| 11.3 | 正則表達式回溯爆炸 (ReDoS) | 惡意輸入 + 不良正則模式 | CPU 100%，單一 regex 執行數分鐘（等效 DoS） |
| 11.4 | `Encoding` 不匹配 | UTF-8 / GBK / Big5 混用 | 亂碼，且可能破壞封包邊界 |
| 11.5 | `string.Substring` 超出範圍 | `str.Substring(10)` 但 str 長度 < 10 | `ArgumentOutOfRangeException` |
| 11.6 | `string.Split` 結果未驗證 | 預期 `"a:b".Split(':')` 得到兩段但輸入沒冒號 | `IndexOutOfRangeException`（存取 `parts[1]`） |
| 11.7 | 文化相關比較 | `"straße".ToUpper()` 在德語文化是 `"STRASSE"` | 字串比較不一致（應用 `StringComparison.Ordinal`） |
| 11.8 | `char` 和 Unicode surrogate pair | emoji 或 CJK 擴展字元佔兩個 char | `string.Length` 不等於可見字元數，截斷可能破壞字元 |

---

## 12. 日期與時間

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 12.1 | `DateTime.Now` vs `DateTime.UtcNow` 混用 | 不同模組用不同的時間基準 | 計算時差差 N 小時（時區偏移） |
| 12.2 | 日光節約時間 (DST) 跳變 | 凌晨 2:00 → 3:00 跳過一小時 | `DateTime(2024,3,10,2,30,0)` 在某些時區不存在 → `ArgumentOutOfRangeException` |
| 12.3 | Unix timestamp 溢位 | 32-bit timestamp 在 2038-01-19 溢位 | 負數時間、日期跳回 1901 |
| 12.4 | 時區轉換 | `TimeZoneInfo.ConvertTime` 找不到時區 | `TimeZoneNotFoundException`（Linux 和 Windows 時區 ID 不同！） |
| 12.5 | `DateTime.Parse` 無指定文化 | 不同 locale 的日期格式不同（MM/dd vs dd/MM） | `FormatException` 或解析出錯誤日期 |
| 12.6 | `Stopwatch` 精度假設 | 假設 `Stopwatch.Frequency` 是固定值 | 虛擬機器或特殊硬體上頻率不同 |
| 12.7 | `DateTime.MinValue` 作為預設 | `default(DateTime)` = `0001-01-01` | 傳給 DB 可能 < MySQL 最小日期 → `MySqlException` |

---

## 13. 檔案與 I/O

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 13.1 | 檔案鎖定 | 其他 process 正在讀寫同一檔案 | `IOException: The process cannot access the file` |
| 13.2 | 路徑超長 | Windows MAX_PATH = 260 (legacy) | `PathTooLongException` |
| 13.3 | 磁碟滿 | 寫入時磁碟空間不足 | `IOException: Not enough space` |
| 13.4 | 路徑注入 | 使用者輸入的檔名含 `../` | 目錄穿越漏洞 |
| 13.5 | `File.ReadAllText` 讀巨大檔案 | 整個檔案載入記憶體 | `OutOfMemoryException` |
| 13.6 | 相對路徑不可靠 | 工作目錄在不同部署環境不同 | `FileNotFoundException` |
| 13.7 | `FileStream` buffer 未 flush | 程式異常結束前資料在 buffer 中 | 資料遺失 |
| 13.8 | 檔案名稱中的非法字元 | `:*?"<>|` 等 | `ArgumentException` / `NotSupportedException` |
| 13.9 | NFS / 網路磁碟延遲 | 掛載的網路磁碟回應慢 | I/O 操作超時、掛起 |

---

## 14. 定時器與排程

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 14.1 | Timer callback 拋異常 | callback 內未 try-catch | `System.Threading.Timer`: 異常在 ThreadPool thread 上拋出，可能終止 process |
| 14.2 | Timer callback 重入 | callback 執行時間 > interval | 多個 callback 同時執行，共享狀態競爭 |
| 14.3 | Timer 漂移 | 系統時間校正（NTP jump）或 GC 暫停 | 排程任務跳過或連續觸發 |
| 14.4 | `System.Timers.Timer` 吞異常 | `SynchronizingObject` 為 null 時，異常被吞 | Bug 被靜默隱藏 |
| 14.5 | Timer 精度 | Windows 預設 timer 精度 15.6ms | `Timer(100ms)` 實際可能 109.2ms、124.8ms |
| 14.6 | Timer 在 Disposed 物件上觸發 | Timer callback 排隊中但物件已被 Dispose | `ObjectDisposedException` 或操作已清理的狀態 |

---

## 15. 反射與動態程式碼

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 15.1 | `Type.GetMethod` 返回 null | 方法名拼錯或方法被 rename | 後續 `.Invoke()` → `NullReferenceException` |
| 15.2 | `MethodInfo.Invoke` 參數型別不匹配 | 裝箱/拆箱錯誤 | `ArgumentException` / `TargetInvocationException` |
| 15.3 | 反射效能 | 高頻呼叫路徑使用反射 | 效能比直接呼叫慢 10-100 倍 |
| 15.4 | `Assembly.Load` 版本衝突 | 同名不同版本的 DLL | `FileLoadException` / `MissingMethodException` |
| 15.5 | 動態程式碼產生記憶體洩漏 | 反覆 `Emit` / `CompileExpression` | 動態 Assembly 無法卸載（.NET Core 3.x 有 ALCs 但需正確使用） |
| 15.6 | `Activator.CreateInstance` 無參數建構子 | 型別沒有無參建構子 | `MissingMethodException` |

---

## 16. 設定與環境

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 16.1 | 設定檔遺失或格式錯誤 | 部署遺漏或手動編輯引入 typo | `FileNotFoundException` / `XmlException` / `FormatException` |
| 16.2 | 環境變數未設定 | `Environment.GetEnvironmentVariable` 返回 null | 後續使用 null 值 |
| 16.3 | 連線字串中的特殊字元 | 密碼含 `;` / `=` 未跳脫 | 連線字串解析錯誤，連線到錯誤的 DB 或失敗 |
| 16.4 | 設定熱更新失敗 | 動態重載設定時舊設定已被捨棄但新設定無效 | 無設定狀態 |
| 16.5 | 設定值越界 | 設 `MaxPlayers = -1` 或 `Port = 99999` | 隱性錯誤或 `ArgumentOutOfRangeException` |
| 16.6 | 大小寫敏感 | Windows 路徑不分大小寫，Linux 分 | 跨平台部署時檔案找不到 |

---

## 17. 安全性

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 17.1 | 封包偽造 | Client 發送偽造的 OpCode / 參數 | 未驗證 → 作弊或 Server 邏輯錯亂 |
| 17.2 | 重放攻擊 | 相同封包重複發送 | 物品複製、金幣翻倍 |
| 17.3 | 速率無限制 | 不限每秒封包數 | 惡意 Client 瘋狂發封包 → Server 過載 |
| 17.4 | 越權操作 | 未驗證操作者身份就執行 | A 玩家修改 B 玩家的資料 |
| 17.5 | 輸入長度無限制 | 玩家名稱/聊天內容無長度上限 | 巨大字串塞爆記憶體 |
| 17.6 | GM 指令洩漏 | GM 操作的 OpCode 未做權限驗證 | 普通玩家發 GM 封包執行特權操作 |
| 17.7 | 時序攻擊 | 密碼比較用 `==` 而非 constant-time compare | 可逐字元推斷密碼 |
| 17.8 | 明文密碼 | 密碼未 hash 直接存 DB | DB 洩漏 → 所有密碼曝光 |
| 17.9 | 隨機數可預測 | `Random` 而非 `RandomNumberGenerator` 產生 token | Token 可預測 → Session hijack |
| 17.10 | 反序列化型別不受限 | 反序列化時接受任意型別 | 遠端程式碼執行 (RCE) |

---

## 18. CLR / Runtime 層級

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 18.1 | `StackOverflowException` | 深度遞迴 | **不可 catch**，直接終止 process |
| 18.2 | `OutOfMemoryException` | 記憶體耗盡或碎片化 | 通常不可恢復 |
| 18.3 | `AccessViolationException` | Native interop 指標錯誤 | .NET Core 預設不可 catch |
| 18.4 | `TypeInitializationException` | 靜態建構子拋異常 | 該型別永久無法使用，後續存取全拋同樣異常 |
| 18.5 | `BadImageFormatException` | 載入了 32-bit DLL 到 64-bit process（或反之） | 啟動失敗 |
| 18.6 | `AppDomain.UnhandledException` | 未捕獲的異常傳播到頂層 | Process crash |
| 18.7 | `ThreadAbortException` (.NET Framework) | `Thread.Abort()` | .NET Core 已不支援但 legacy 代碼可能殘留 |
| 18.8 | GC suspension 掛起 | 所有 managed 執行緒必須到達 safe point | 某執行緒在 tight loop 中不 yield → GC 掛數秒 |
| 18.9 | `ExecutionEngineException` | CLR 內部錯誤 | 極罕見但無法處理 |
| 18.10 | JIT 編譯錯誤 | 極罕見的 JIT bug | 產出錯誤的機器碼，行為不可預測 |

---

## 19. Interop 與 Native

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 19.1 | P/Invoke 簽名不匹配 | Marshal 型別宣告與 native 函式不符 | Stack corruption、`AccessViolationException` |
| 19.2 | Native 記憶體洩漏 | `Marshal.AllocHGlobal` 未配對 `FreeHGlobal` | 記憶體持續增長（GC 不管非托管記憶體） |
| 19.3 | Callback 被 GC | 傳給 native 的 delegate 被 GC 回收 | Native code 回呼已回收的 delegate → **Crash** |
| 19.4 | 字串 Marshaling | ANSI/Unicode/UTF-8 不匹配 | 亂碼或 buffer overrun |
| 19.5 | 結構體對齊 | `StructLayout` pack 不匹配 | 欄位偏移錯誤，讀到錯誤資料 |
| 19.6 | DLL 找不到 | Native DLL 路徑不對或缺依賴 | `DllNotFoundException` |

---

## 20. .NET Core 特有問題

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 20.1 | `.NET Core 3.1` 已 EOL | 無安全更新 | 已知漏洞無法修補 |
| 20.2 | `System.Text.Json` 行為差異 | 與 `Newtonsoft.Json` 預設行為不同（嚴格模式） | 反序列化失敗 |
| 20.3 | Linux 檔案路徑大小寫 | 開發用 Windows（不敏感），部署到 Linux（敏感） | `FileNotFoundException` |
| 20.4 | `HttpClient` 在 Linux 上的 DNS | Linux 不像 Windows 有 OS-level DNS cache | 頻繁 DNS 查詢拖慢效能 |
| 20.5 | Kestrel 連線限制 | 預設限制可能不適合遊戲 Server 的連線模式 | 連線被拒 |
| 20.6 | `AssemblyLoadContext` 洩漏 | 動態載入 Assembly 但 ALC 被殘留引用 | 永遠無法卸載 → 記憶體洩漏 |
| 20.7 | globalization invariant mode | Docker 中設了 `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=true` | `CultureNotFoundException` 或排序異常 |
| 20.8 | Ready-to-Run (R2R) 圖片 mismatch | 發布時的 RID 與運行環境不匹配 | 啟動時 fallback 到 JIT，效能降級（非異常但驚人的慢） |

---

## 21. 邏輯層級危險

### 21.1 狀態機錯誤
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 21.1.1 | 非法狀態轉換 | 從「死亡」直接轉到「攻擊」而不經過「復活」 | 遊戲邏輯混亂 |
| 21.1.2 | 狀態不同步 | Server 和 Client 的狀態不一致 | 客戶端表現異常、外掛利用 |
| 21.1.3 | 狀態殘留 | 進入新狀態時舊狀態的 flag 沒清除 | 累積的 flag 互相干擾 |

### 21.2 併發邏輯錯誤
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 21.2.1 | TOC-TOU (Time-of-check to time-of-use) | 先檢查背包有空位，再放物品——但中間被插入其他操作 | 背包溢出、物品複製 |
| 21.2.2 | 雙花 (Double-spending) | 同時發兩個「使用道具」的封包 | 道具被使用兩次 |
| 21.2.3 | ABA 問題 | 值從 A 變 B 再變回 A，CAS 判斷為「沒變」 | 跳過應執行的邏輯 |

### 21.3 數值設計
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 21.3.1 | 負數未防護 | 攻擊力為負 → 攻擊反而加血 | 遊戲破壞 |
| 21.3.2 | 乘法溢位 | 傷害 * 暴擊倍率 * BUFF 倍率 超過 int.MaxValue | wrap around 成負數或極小正數 |
| 21.3.3 | 浮點累積誤差 | 每幀 `position += speed * deltaTime` | 長時間後位置偏移明顯 |
| 21.3.4 | 除以零 | 某個分母是動態計算的（如隊伍人數） | `DivideByZeroException` 或 `NaN` 傳播 |

### 21.4 生命週期
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 21.4.1 | 物件已銷毀但仍被引用 | 玩家下線但 Timer callback 仍在觸發 | `NullReferenceException` 或操作已清理的資料 |
| 21.4.2 | 初始化順序依賴 | Manager A 初始化時存取尚未初始化的 Manager B | 讀到 null 或空集合 |
| 21.4.3 | 關服時的 race | Shutdown 過程中仍有封包到達 | 操作已關閉的資源 |
| 21.4.4 | 重入 (Reentrancy) | Handler 處理封包的過程中觸發事件，事件處理器又呼叫同一 Handler | 狀態不一致、Stack Overflow |

---

## 22. Log 與診斷的反噬

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 22.1 | Log 格式化拋異常 | `string.Format` 參數不匹配 | 本來只是想記 log 結果反而拋了異常 |
| 22.2 | Log I/O 阻塞 | 同步寫檔案 log，磁碟 I/O 慢 | 遊戲主迴圈被 log 拖慢 |
| 22.3 | Log 檔案無限增長 | 無 rotation / 無大小限制 | 磁碟滿 → 所有 I/O 失敗 |
| 22.4 | Log 洩露敏感資訊 | 把密碼、token、完整封包內容寫入 log | 安全風險 |
| 22.5 | 高頻 log 造成 GC 壓力 | 每個封包都 `$"Received {opCode} from {playerId}"` | 大量臨時字串分配 |
| 22.6 | 異常的 `ToString()` 遞迴 | 自訂型別的 `ToString()` 存取了會拋異常的屬性 | Log 異常時反而觸發新異常 |
| 22.7 | `Stopwatch` / 效能計數器的 overhead | 在每個封包上都做計時 | 累積的計時開銷本身就成為效能瓶頸 |

---

## 統計摘要

| 分類 | 項目數 |
|------|--------|
| 1. 執行緒與併發 | 21 |
| 2. 集合操作 | 11 |
| 3. Async/Await | 13 |
| 4. 記憶體與 GC | 15 |
| 5. 網路與 Socket | 17 |
| 6. 資料庫 | 14 |
| 7. 序列化 | 13 |
| 8. Null 參照 | 9 |
| 9. 型別轉換與溢位 | 10 |
| 10. 資源管理 | 7 |
| 11. 字串處理 | 8 |
| 12. 日期與時間 | 7 |
| 13. 檔案與 I/O | 9 |
| 14. 定時器與排程 | 6 |
| 15. 反射與動態程式碼 | 6 |
| 16. 設定與環境 | 6 |
| 17. 安全性 | 10 |
| 18. CLR / Runtime | 10 |
| 19. Interop 與 Native | 6 |
| 20. .NET Core 特有 | 8 |
| 21. 邏輯層級危險 | 14 |
| 22. Log 與診斷 | 7 |
| **總計** | **~227 項** |

---
---

# Part 2: C# Server 壞味道全集（Code Smells）

> 壞味道 ≠ Bug。壞味道是**尚未爆炸的結構性問題**——它們讓程式碼更難理解、更難維護、更容易在未來引發 Part 1 的異常。
> 分類依據：Martin Fowler《Refactoring》、Robert C. Martin《Clean Code》、遊戲伺服器實戰、.NET 社群共識。

---

## 目錄（Part 2）

23. [命名壞味道](#23-命名壞味道)
24. [方法層級壞味道](#24-方法層級壞味道)
25. [類別層級壞味道](#25-類別層級壞味道)
26. [繼承與多型壞味道](#26-繼承與多型壞味道)
27. [耦合壞味道](#27-耦合壞味道)
28. [資料結構壞味道](#28-資料結構壞味道)
29. [錯誤處理壞味道](#29-錯誤處理壞味道)
30. [併發設計壞味道](#30-併發設計壞味道)
31. [效能壞味道](#31-效能壞味道)
32. [架構壞味道](#32-架構壞味道)
33. [遊戲伺服器特有壞味道](#33-遊戲伺服器特有壞味道)
34. [C# 語言特有壞味道](#34-c-語言特有壞味道)
35. [測試壞味道](#35-測試壞味道)
36. [部署與配置壞味道](#36-部署與配置壞味道)

---

## 23. 命名壞味道

| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 23.1 | **神祕命名** | 變數叫 `d`, `tmp`, `val`, `data`, `info` | 三個月後沒人知道這是什麼，包括自己 |
| 23.2 | **匈牙利命名殘留** | `strName`, `intCount`, `lstPlayers` | 型別變了名字不會跟著改，製造假資訊 |
| 23.3 | **名不副實** | `ProcessData()` 實際上做了驗證+儲存+通知 | 呼叫者無法預期副作用 |
| 23.4 | **布林反邏輯** | `isNotReady`, `disableCheck` | 雙重否定 `if (!isNotReady)` 腦袋打結 |
| 23.5 | **數字後綴** | `handler1`, `handler2`, `manager3` | 語義不清，增刪時序號意義消失 |
| 23.6 | **縮寫不一致** | 有人寫 `Mgr`、有人寫 `Manager`、有人寫 `Mngr` | 搜尋不到、IDE 自動完成失效 |
| 23.7 | **動詞/名詞混淆** | 類別叫 `Calculate`（動詞）、方法叫 `PlayerManager`（名詞） | 職責邊界模糊 |
| 23.8 | **意義過載** | `id` 有時是玩家 ID，有時是物品 ID，有時是 DB row ID | 同名不同義，出錯時極難追蹤 |
| 23.9 | **拼寫錯誤固化** | `Recieve`, `Destory`, `Bindding` 已散布全 codebase | 每個新人都在猜正確拼法，搜尋變噩夢 |

---

## 24. 方法層級壞味道

### 24.1 方法體積
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 24.1.1 | **巨型方法 (Long Method)** | 單一方法超過 100 行 | 無法一眼掌握邏輯，bug 藏在深處 |
| 24.1.2 | **深層巢狀** | `if { if { if { for { if { ... }}}}}` 超過 3~4 層 | 認知負荷爆表，邊界條件極易遺漏 |
| 24.1.3 | **過長參數列** | 方法有 6+ 個參數 | 呼叫者容易搞錯順序（特別是相同型別連續出現） |
| 24.1.4 | **旗標參數 (Flag Argument)** | `Process(data, true, false, true)` | 呼叫端無法理解每個 bool 是什麼意思 |
| 24.1.5 | **Output 參數過多** | 3+ 個 `out` / `ref` 參數 | 方法想返回太多東西，職責不清 |

### 24.2 方法行為
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 24.2.1 | **副作用隱藏** | `GetPlayer()` 裡面偷偷修改了全域狀態 | 呼叫者不知道 Get 會改東西 |
| 24.2.2 | **指令/查詢未分離 (CQS violation)** | 同一方法既修改狀態又返回值 | 無法安全地重試或快取結果 |
| 24.2.3 | **死碼 (Dead Code)** | 永遠不會被呼叫的方法、永遠為 false 的分支 | 增加閱讀成本，誤導維護者 |
| 24.2.4 | **註解掉的程式碼** | 大段 `// old implementation...` 留在 codebase | 不確定能不能刪、為什麼留、是否還有用 |
| 24.2.5 | **上帝方法 (God Method)** | 一個方法做了所有事：驗證+查DB+計算+發封包+記 log | 無法單獨測試任何一部分 |
| 24.2.6 | **時間耦合** | 必須按特定順序呼叫 `Init()` → `Load()` → `Start()` 否則爆炸 | 編譯器不會幫你檢查呼叫順序 |

---

## 25. 類別層級壞味道

### 25.1 職責問題
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 25.1.1 | **上帝類別 (God Class)** | 單一類別超過 2000 行、50+ 方法 | 改任何功能都要碰這個類別，合併衝突不斷 |
| 25.1.2 | **資料泥團 (Data Clump)** | 總是一起出現的參數：`(int x, int y, int z)` 到處傳 | 應該封裝成 `Vector3` 但到處都是裸參數 |
| 25.1.3 | **純資料類 (Anemic Domain Model)** | class 只有 getter/setter，邏輯全在外面的 Manager | 資料和行為分離 → 邏輯散落四處，修改一個欄位要改 N 個地方 |
| 25.1.4 | **過度親密 (Inappropriate Intimacy)** | A 類直接存取 B 類的 private 成員（透過 internal/friend/反射） | 耦合到實作細節，B 改內部結構時 A 必跟著壞 |
| 25.1.5 | **特性嫉妒 (Feature Envy)** | A 的方法大量使用 B 的成員，幾乎不碰自己的 | 邏輯放錯地方了 |
| 25.1.6 | **拒絕遺產 (Refused Bequest)** | 子類繼承了父類但 override 大部分方法為空或拋異常 | 繼承關係不合理 |

### 25.2 設計問題
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 25.2.1 | **Singleton 濫用** | 到處 `XXManager.Instance.DoSomething()` | 隱藏依賴、無法測試、初始化順序不可控 |
| 25.2.2 | **靜態方法濫用** | `static class Utility` 成了垃圾桶 | 無法 mock/替換、隱性全域狀態 |
| 25.2.3 | **過度封裝** | 簡單邏輯被包了 5 層 wrapper | 追蹤一個呼叫要跳 5 個檔案 |
| 25.2.4 | **Primitive Obsession** | 用 `int` 表示玩家 ID、物品 ID、地圖 ID——全是 int | 參數傳錯不會編譯報錯（把 itemId 傳給 playerId 參數） |
| 25.2.5 | **平行繼承 (Parallel Inheritance)** | 加一種怪物就要加 `MonsterA`, `MonsterABehavior`, `MonsterARenderer`... | 新增一種類型要同時改 N 個繼承樹 |
| 25.2.6 | **幽靈類別 (Lazy Class)** | 類別只有 1-2 個方法，做的事極簡單 | 增加間接層但不增加價值 |
| 25.2.7 | **中間人 (Middle Man)** | 類別的所有方法都只是 delegate 給另一個類別 | 無意義的轉發層 |

---

## 26. 繼承與多型壞味道

| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 26.1 | **深繼承樹** | 5+ 層繼承 | 理解一個方法要向上追溯 5 個類別 |
| 26.2 | **菱形問題模擬** | 多層繼承 + interface default implementation | 行為來源不明確 |
| 26.3 | **基類變更恐懼** | 不敢改基類因為不知道有多少子類依賴 | 基類腐化——堆積永遠不用但不敢刪的舊方法 |
| 26.4 | **instanceof/is 鏈** | `if (obj is TypeA) ... else if (obj is TypeB) ...` | 加一種新類型就要改所有判斷鏈，且容易漏 |
| 26.5 | **Switch on Type** | `switch (entity.Type) { case Monster: ... case NPC: ... }` | 同 26.4，應用多型取代 |
| 26.6 | **強制向下轉型** | 到處 `(SpecificType)baseReference` | 如果實際型別變了就炸，破壞多型意義 |
| 26.7 | **Liskov 違反** | 子類的行為和父類承諾的不同（如子類丟 `NotSupportedException`） | 使用父類引用的代碼在遇到這個子類時爆炸 |
| 26.8 | **空 virtual override** | `override void OnUpdate() { }` 什麼都不做 | 如果父類預期 override 有行為，可能導致邏輯遺漏 |
| 26.9 | **繼承只為了重用代碼** | 不是 IS-A 關係卻用繼承（如 `PlayerManager : Dictionary<int,Player>`） | 暴露了不該暴露的 API，語義扭曲 |

---

## 27. 耦合壞味道

| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 27.1 | **循環依賴** | A 引用 B，B 引用 A | 無法獨立編譯、測試、部署任一方 |
| 27.2 | **上帝物件傳遞** | 把整個 `GameClient` / `Player` 物件傳進每個方法 | 方法拿到的權限遠超它需要的，改了不該改的東西 |
| 27.3 | **全域可變狀態** | `public static Dictionary<int, Player> AllPlayers` | 任何地方都能改，race condition 天堂 |
| 27.4 | **魔術數字 / 字串** | `if (type == 3)`, `if (name == "special_item")` | 意義不明，散布各處，改一個要全 grep |
| 27.5 | **隱式時序依賴** | A 必須在 B 之前執行但只在文件裡寫了（或沒寫） | 有人調換順序就壞，編譯器不會提醒 |
| 27.6 | **Shotgun Surgery** | 修改一個功能要改 10+ 個檔案 | 改漏一個就是 bug |
| 27.7 | **發散式修改 (Divergent Change)** | 同一個檔案因為不同原因被不同人頻繁修改 | 合併衝突、職責混亂 |
| 27.8 | **知識重複 (DRY 違反)** | 同一段業務規則出現在 3+ 個地方 | 改了一處忘了其他 → 行為不一致 |
| 27.9 | **隱式協定** | 兩個系統靠「欄位名相同」或「存取同一張 DB 表」耦合 | 改了欄位名一方不知道另一方也在用 |
| 27.10 | **Train Wreck (火車殘骸)** | `ctx.GetService().GetManager().GetPlayer().GetBag().GetItem(id)` | 中途任一環節改了介面，整串全斷 |

---

## 28. 資料結構壞味道

| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 28.1 | **萬能字典** | `Dictionary<string, object>` 當萬用容器 | 沒有編譯期型別檢查，key 拼錯 runtime 才爆 |
| 28.2 | **Tuple 濫用** | 方法回傳 `(int, string, bool, List<int>)` | 呼叫者 `result.Item3` 完全不知是什麼 |
| 28.3 | **混合容器** | `List<object>` 裡混放不同型別 | 取出時必須 cast，cast 錯就炸 |
| 28.4 | **過大 DTO** | 一個 DTO / Message 有 50+ 欄位 | 大部分場景只用到 5 個欄位，其他白白傳輸/序列化 |
| 28.5 | **可變共享資料** | 同一個物件被多處引用且可修改 | A 改了，B 不知道被改了 |
| 28.6 | **集合暴露** | `public List<Item> Items { get; set; }` | 外部可以 `.Clear()` / `.Add()` 繞過業務規則 |
| 28.7 | **巢狀集合** | `Dictionary<int, Dictionary<int, List<Tuple<int,string>>>>` | 程式碼幾乎不可讀，重構極困難 |
| 28.8 | **字串驅動邏輯** | 用字串當 key 區分邏輯（`if (action == "attack")`） | 拼錯就靜默失敗，無法用 IDE 重構 |

---

## 29. 錯誤處理壞味道

| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 29.1 | **空 catch (Swallowed Exception)** | `catch (Exception) { }` | Bug 被完全隱藏，症狀在遙遠的地方才浮現 |
| 29.2 | **Pokemon catch** | `catch (Exception ex) { Log(ex); }` 包住整個方法 | 所有異常一視同仁，無法區分可恢復與不可恢復 |
| 29.3 | **異常當流程控制** | 用 `try { int.Parse(s); } catch { ... }` 代替 `TryParse` | 效能差 100 倍，混淆異常/正常路徑 |
| 29.4 | **回傳碼與異常混用** | 有些方法回傳 `-1` 表示失敗，有些拋異常 | 呼叫者不知道該檢查回傳值還是 try-catch |
| 29.5 | **異常資訊不足** | `throw new Exception("Error")` | 無法定位問題：哪個玩家？什麼操作？什麼參數？ |
| 29.6 | **重新拋出遺失堆疊** | `catch (Exception ex) { throw ex; }` 而非 `throw;` | Stack trace 從 catch 處重新開始，原始呼叫棧丟失 |
| 29.7 | **過度防禦** | 每一行都 try-catch，每個參數都判 null | 程式碼膨脹 3 倍，真正的問題被淹沒 |
| 29.8 | **忽略 async 異常** | `async void` 或 `_ = SomeAsync()` | 異常被吞（Part 1 的 3.1.3 / 3.2.1），壞味道版 |
| 29.9 | **自訂 Exception 無序列化** | 自訂 Exception 沒實作序列化建構子 | 跨 AppDomain 或 Remoting 時遺失異常資訊 |
| 29.10 | **錯誤碼不統一** | 模組 A 回 `-1` 表示找不到，模組 B 回 `0` 表示找不到 | 呼叫者搞混錯誤碼的含義 |

---

## 30. 併發設計壞味道

| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 30.1 | **鎖粒度太大** | 整個方法用一把大鎖包住 | 併發度趨近於零，Server 退化成單執行緒 |
| 30.2 | **鎖粒度太小** | 每個欄位一把鎖 | 組合操作不原子，且死鎖機率上升 |
| 30.3 | **未標記執行緒模型** | 不知道這個類別是設計給單執行緒還是多執行緒用的 | 新人隨意在多執行緒環境呼叫 → race |
| 30.4 | **lock(this) / lock(typeof)** | 用公開可見的物件當鎖 | 外部程式碼也可能鎖同一物件 → 死鎖 |
| 30.5 | **lock(string)** | 字串 intern 池導致不相關的程式碼共用同一把鎖 | 不可預期的阻塞 |
| 30.6 | **雙重檢查鎖定 (DCL) 寫錯** | 缺少 `volatile` 或 `Interlocked` | 讀到半初始化的物件 |
| 30.7 | **同步集合的假安全感** | `ConcurrentDictionary` 的單一操作安全 ≠ 複合操作安全 | 先讀後寫不原子 |
| 30.8 | **Thread.Sleep 替代適當同步** | 用 `Sleep(100)` 「等」另一個執行緒做完 | 不可靠（來不及/浪費時間），且佔住 ThreadPool thread |
| 30.9 | **無界佇列** | `ConcurrentQueue` 或 `Channel` 沒有設 bounded capacity | 生產速度 > 消費速度 → 記憶體無限增長 |
| 30.10 | **業務邏輯與執行緒管理混合** | Handler 裡手動 `new Thread()` / `Task.Run()` | 難以追蹤、難以控制並發數、難以 graceful shutdown |

---

## 31. 效能壞味道

### 31.1 記憶體分配
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 31.1.1 | **熱路徑上 new 物件** | 每個封包處理都 `new List<T>()`, `new byte[]` | GC 壓力，遊戲每隔幾秒卡一下 |
| 31.1.2 | **LINQ 在熱路徑** | `.Where().Select().ToList()` 在每幀/每封包執行 | 產生大量中間 IEnumerable / delegate 物件 |
| 31.1.3 | **Boxing 在高頻路徑** | `object key = intValue;` 或 `dict[structKey]`（未自訂 comparer） | 每次 box 都是一次 heap 分配 |
| 31.1.4 | **string interpolation 在非必要路徑** | `$"Player {id} action {action}"` 即使 log level 不夠也會求值 | 白白分配字串 |
| 31.1.5 | **params array 在熱路徑** | `void Log(params object[] args)` 每次呼叫都 new 陣列 | 隱性 heap 分配 |

### 31.2 算法與結構
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 31.2.1 | **O(n) 查找代替 O(1)** | 用 `List.Find()` 而非 `Dictionary` | 玩家多時效能劇烈下降 |
| 31.2.2 | **重複計算** | 迴圈內反覆計算不會變的值 | 浪費 CPU |
| 31.2.3 | **不必要的排序** | `list.OrderBy().First()` 只要最小值卻排了全部 | O(n log n) vs O(n) |
| 31.2.4 | **大量 string.Contains / StartsWith 比對** | 線性掃描字串匹配 | 應該用 Dictionary / HashSet / Trie |
| 31.2.5 | **序列化-反序列化做深複製** | `Deserialize(Serialize(obj))` 當 DeepClone 用 | 極慢且 GC 壓力大 |

### 31.3 I/O 效能
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 31.3.1 | **同步 I/O 在非同步上下文** | async 方法內呼叫 `File.ReadAllText`（同步版） | 阻塞 ThreadPool thread |
| 31.3.2 | **頻繁小寫入** | 每條 log / 每筆資料都立即 flush 到磁碟 | I/O 成為瓶頸 |
| 31.3.3 | **N+1 DB/Network 呼叫** | 迴圈內逐筆 query | round-trip 延遲 * N |
| 31.3.4 | **未使用 buffer pool** | 每次 I/O 都新建 byte[] buffer | 分配壓力 + LOH 碎片 |

---

## 32. 架構壞味道

### 32.1 分層問題
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 32.1.1 | **層跳越 (Layer Skipping)** | Handler 直接存取 DB 繞過 Manager | 業務邏輯散落在不同層，規則無法統一執行 |
| 32.1.2 | **Leaky Abstraction** | 上層需要知道下層的實作細節才能正確使用 | 抽象層失去價值 |
| 32.1.3 | **貧血服務層** | Service / Manager 只做 CRUD 轉發 | 層的存在不增加價值 |
| 32.1.4 | **循環分層** | 下層反向呼叫上層 | 編譯能過但邏輯混亂，改動漣漪不可控 |

### 32.2 模組問題
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 32.2.1 | **模組邊界不清** | 玩家資料在 PlayerManager, BagManager, EquipManager 都有一份 | 修改一個功能要跨 N 個 Manager |
| 32.2.2 | **共用資料庫直連** | 不同服務直接讀寫同一張 DB 表 | 隱式耦合——改表結構要通知所有服務 |
| 32.2.3 | **訊息格式不版本化** | Proto / 封包格式改了就直接改，不保留相容性 | 滾動更新時新舊版本 Server/Client 共存會崩 |
| 32.2.4 | **部署單體** | 所有服務必須同時部署 | 改一行代碼要重啟整個叢集 |

### 32.3 狀態管理
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 32.3.1 | **分散式狀態不一致** | 玩家狀態在 MapServer 和 GuildServer 各有一份 | 更新一邊忘了另一邊 → 資料分裂 |
| 32.3.2 | **快取未失效** | 快取了資料但沒有失效/更新機制 | 讀到過期資料 |
| 32.3.3 | **Session 狀態過大** | 每個玩家連線在記憶體中 hold 大量資料 | 5000 玩家 × 100KB = 500MB |
| 32.3.4 | **Global 狀態當作配置傳遞** | 設定值存在 static 變數而非注入 | 無法切換配置（如測試 vs 正式環境） |

---

## 33. 遊戲伺服器特有壞味道

### 33.1 封包處理
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 33.1.1 | **Handler 內 DB 操作** | 收到封包 → 直接查 DB | 如果 DB 慢，主迴圈卡住所有玩家 |
| 33.1.2 | **未驗證封包參數** | `var itemId = packet.ReadInt32(); Use(itemId);` 沒驗證 | Part 1 的 17.1，壞味道版本：結構上就沒有驗證層 |
| 33.1.3 | **封包處理無限制** | 一個玩家一幀可發任意數量封包 | 惡意 Client 發 10000 封包/秒拖垮 Server |
| 33.1.4 | **同步封包廣播** | 對 1000 個玩家 for 迴圈 `Send()` | 最後一個玩家等前面 999 個都送完 |
| 33.1.5 | **封包大小未檢查** | 無最大封包大小限制 | 攻擊者發送超大封包消耗記憶體 |

### 33.2 遊戲邏輯
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 33.2.1 | **硬編碼遊戲數值** | `if (level >= 60)`, `damage *= 1.5f` | 企劃改數值要改程式碼、重新編譯、重新部署 |
| 33.2.2 | **戰鬥結果 Client 說了算** | Client 直接發「我打了 9999 傷害」 | 外掛天堂 |
| 33.2.3 | **AOE 無上限** | 範圍技能遍歷地圖上所有實體 | 萬人同屏時 O(n²) 爆炸 |
| 33.2.4 | **Tick Rate 不穩定** | 主迴圈用 `Thread.Sleep` 控制幀率 | GC 或 I/O 導致單幀超時 → 後續幀追趕 → 物理/邏輯不穩 |
| 33.2.5 | **事件廣播無篩選** | 有人撿了一個物品 → 全服所有人收到通知 | 頻寬與 CPU 浪費 |
| 33.2.6 | **無髒標記的全量推送** | 玩家屬性任何一個欄位改了就推送整個 proto | 頻寬浪費 10-100 倍 |

### 33.3 資源管理
| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 33.3.1 | **物件池未使用** | 高頻建立/銷毀的物件（彈幕、特效、封包 buffer）沒有池化 | GC 壓力 |
| 33.3.2 | **下線後殘留引用** | 玩家斷線但隊伍/公會/好友列表仍持有引用 | 記憶體洩漏 + 操作已清理的物件 |
| 33.3.3 | **地圖/場景資源不釋放** | 動態副本結束但地圖物件不回收 | 記憶體持續增長直到 OOM |
| 33.3.4 | **定時器跟隨擁有者生命週期** | 玩家擁有的定時器在玩家下線後仍在跑 | Timer callback 存取已清理的資料 |

---

## 34. C# 語言特有壞味道

| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 34.1 | **struct 可變性** | `mutable struct` + 裝箱 / 集合操作 | 修改的是副本而非原物件，變更無效 |
| 34.2 | **operator== 不覆寫** | class 只覆寫 `Equals` 不覆寫 `==` | `obj1 == obj2` 和 `obj1.Equals(obj2)` 結果不同 |
| 34.3 | **IDisposable 不實作 pattern** | 忘了 `GC.SuppressFinalize`，或 Finalizer 裡存取託管物件 | 資源洩漏或 Finalizer 異常 |
| 34.4 | **event 在宣告類別外 `= null`** | 只有宣告類別能直接 assign event | 編譯報錯（C# 防護），但用反射繞過就是 bug |
| 34.5 | **ValueTask 多次 await** | `ValueTask` 只能 await 一次 | 第二次 await 行為未定義 |
| 34.6 | **Span/Memory 逃逸** | 把 `Span<T>` 存到欄位（編譯器會擋）或把 `Memory<T>` 的底層 array 傳出 | 底層 buffer 被回收後存取 → 損壞 |
| 34.7 | **async method 裡的 `using`** | `using var stream = ...;` 在 await 之後 stream 還活著 | 如果 Task 被 cancel，Dispose timing 可能不如預期 |
| 34.8 | **Extension method 隱藏實體方法** | Extension 與實體方法同名但簽名不同 | 編譯器優先選實體方法，行為可能和開發者預期不同 |
| 34.9 | **enum 未加 [Flags] 卻做位元運算** | `MyEnum.A | MyEnum.B` 結果是未定義的 enum 值 | `ToString()` 顯示數字而非名稱，且 switch 不匹配 |
| 34.10 | **Nullable Reference Types 只在部分啟用** | 一半程式碼啟用 NRT，一半沒有 | 假安全感——跨邊界時 null 仍會偷渡進來 |
| 34.11 | **隱式轉換運算子** | `public static implicit operator int(MyType t)` | 在不預期的地方發生轉換，debug 困難 |
| 34.12 | **default(T) 的陷阱** | `default(MyClass)` = null, `default(int)` = 0, `default(bool)` = false | 泛型程式碼中 `if (value == default)` 對引用型別是 null check，對值型別是零值 check |

---

## 35. 測試壞味道

| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 35.1 | **零測試** | 整個專案沒有 unit test | 每次修改都是盲飛，回歸靠人肉 |
| 35.2 | **只測 Happy Path** | 只測正常流程，不測邊界/錯誤/併發 | 生產環境不會只走 happy path |
| 35.3 | **測試依賴外部服務** | 測試跑起來要連 DB / Redis / 第三方 API | CI 不穩定、本地開發被 block |
| 35.4 | **測試之間有順序依賴** | Test A 建立資料，Test B 用 A 的資料 | 單獨跑 B 會失敗，平行化會失敗 |
| 35.5 | **魔術 assert** | `Assert.AreEqual(42, result)` 42 哪來的？ | 測試本身成了需要測試的東西 |
| 35.6 | **過度 Mock** | Mock 了所有依賴，測試只在驗證 mock 的呼叫次數 | 改了實作，mock 全壞，但真的 bug 反而測不到 |
| 35.7 | **冰淇淋反模式** | 大量 E2E 測試，幾乎沒有 unit test | 回饋慢（跑一次 30 分鐘）、失敗原因不明確 |
| 35.8 | **Flaky Test** | 測試時過時不過 | 團隊開始忽略測試失敗（「又是那個不穩的 test」） |
| 35.9 | **測試和實作耦合** | 測試直接存取 private 成員 | 重構內部結構時測試全壞，但功能其實沒問題 |

---

## 36. 部署與配置壞味道

| # | 壞味道 | 特徵 | 為何危險 |
|---|--------|------|---------|
| 36.1 | **手動部署** | 靠人記得步驟，無自動化腳本 | 漏一步就爆，壓力下更容易出錯 |
| 36.2 | **設定散落多處** | 部分在 XML、部分在環境變數、部分硬編碼 | 找不到某個設定在哪裡改 |
| 36.3 | **無回滾計畫** | 部署失敗沒有快速回退方案 | 只能往前修，停服時間拉長 |
| 36.4 | **dev/prod 設定混淆** | 開發環境的 DB 連線字串殘留在 prod 設定中 | 生產打到開發 DB 或反之 |
| 36.5 | **密鑰硬編碼** | API Key / DB 密碼寫在原始碼中 | Git 歷史永久保留密鑰 |
| 36.6 | **版本號未管理** | 無法分辨線上跑的是哪個版本 | 出問題時不知道該查哪個 commit |
| 36.7 | **單點故障無備援** | 關鍵服務（如 AccountServer）只有一個實例 | 掛了全服不能登入 |
| 36.8 | **Log 和 Config 混在可執行檔目錄** | 更新時容易覆蓋 log / config | 資料遺失 |
| 36.9 | **無健康檢查 (Health Check)** | 服務掛了要人發現 | 玩家先於維運團隊知道 Server 掛了 |
| 36.10 | **監控盲區** | 沒有 metrics：記憶體、連線數、封包延遲、GC 暫停 | 效能慢慢惡化但無人察覺，直到崩潰 |

---

## Part 2 統計摘要

| 分類 | 項目數 |
|------|--------|
| 23. 命名壞味道 | 9 |
| 24. 方法層級壞味道 | 11 |
| 25. 類別層級壞味道 | 13 |
| 26. 繼承與多型壞味道 | 9 |
| 27. 耦合壞味道 | 10 |
| 28. 資料結構壞味道 | 8 |
| 29. 錯誤處理壞味道 | 10 |
| 30. 併發設計壞味道 | 10 |
| 31. 效能壞味道 | 13 |
| 32. 架構壞味道 | 12 |
| 33. 遊戲伺服器特有壞味道 | 15 |
| 34. C# 語言特有壞味道 | 12 |
| 35. 測試壞味道 | 9 |
| 36. 部署與配置壞味道 | 10 |
| **Part 2 小計** | **~151 項** |

---

---
---

# Part 3: 確定缺漏的獨立主題

> Part 1-2 遺漏的完整獨立領域。每一項都是在實際 C# Server 營運中會獨立遇到的問題群。

---

## 目錄（Part 3）

37. [Process 生命週期與信號處理](#37-process-生命週期與信號處理)
38. [Container / Docker 特有問題](#38-container--docker-特有問題)
39. [快取專題](#39-快取專題)
40. [背壓與流量控制 (Backpressure)](#40-背壓與流量控制-backpressure)
41. [資料持久化與崩潰恢復](#41-資料持久化與崩潰恢復)
42. [依賴管理 (NuGet / DLL)](#42-依賴管理-nuget--dll)
43. [第三方函式庫陷阱](#43-第三方函式庫陷阱)
44. [加密與密碼學深度](#44-加密與密碼學深度)
45. [網路拓撲與負載均衡](#45-網路拓撲與負載均衡)
46. [升級與遷移風險](#46-升級與遷移風險)
47. [人為操作失誤 (Operational Error)](#47-人為操作失誤-operational-error)
48. [國際化與在地化深度 (i18n/L10n)](#48-國際化與在地化深度-i18nl10n)
49. [熱更新 / 動態載入](#49-熱更新--動態載入)
50. [分散式系統基本問題](#50-分散式系統基本問題)

---

## 37. Process 生命週期與信號處理

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 37.1 | **SIGTERM 未處理** | Linux 上 `kill` / Docker `stop` 送 SIGTERM，process 不理會 | 10 秒後被 SIGKILL 強殺 → 資料未存檔、連線未優雅關閉 |
| 37.2 | **SIGINT 和 SIGTERM 行為不一致** | Ctrl+C (SIGINT) 有處理但 SIGTERM 沒有 | 開發時正常（Ctrl+C），部署後被強殺 |
| 37.3 | **Graceful Shutdown 順序錯誤** | 先關 DB 連線，再嘗試存檔玩家資料 | 存檔失敗，玩家進度遺失 |
| 37.4 | **Shutdown 超時無上限** | 等待所有玩家存檔完成才關閉，但某些存檔卡住 | Process 永遠不關閉，維運被迫強殺 |
| 37.5 | **Shutdown 期間仍接受新連線** | 停止接受封包但不停止 accept 新連線 | 新連入的玩家進入半死狀態 |
| 37.6 | **Orphan 子 Process** | 主 Process 啟動了子 Process 但崩潰時未連帶終止 | 殭屍 Process 佔用 Port / 記憶體 |
| 37.7 | **PID 檔案殘留** | 上次崩潰沒刪 PID 檔案 | 新實例看到 PID 檔以為已有實例在跑 → 拒絕啟動 |
| 37.8 | **Process 重啟風暴** | Watchdog 偵測到 crash → 立即重啟 → 又 crash → 再重啟 | CPU 打滿，日誌灌爆磁碟 |
| 37.9 | **Console.CancelKeyPress 吞掉中斷** | 在 handler 中設 `e.Cancel = true` 但後續清理卡住 | 使用者按 Ctrl+C 後 process 掛住，只能用 kill -9 |
| 37.10 | **AppDomain.ProcessExit 時間限制** | .NET 的 ProcessExit 事件預設只有幾秒執行時間 | 清理邏輯做到一半被截斷 |
| 37.11 | **未註冊 UnhandledException handler** | 未知異常到達頂層 | 無 log、無 dump、process 靜默消失 |
| 37.12 | **Environment.FailFast 的副作用** | 呼叫 `FailFast` 不會執行 finally / Dispose | 所有 pending 的 I/O 被截斷，buffer 中的資料遺失 |

---

## 38. Container / Docker 特有問題

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 38.1 | **記憶體上限 vs GC 不知情** | Container memory limit 4GB 但 .NET GC 看到宿主機 64GB | GC 不積極回收 → 觸及 cgroup 上限 → **OOM Killer 直接殺 process**（無 Exception） |
| 38.2 | **CPU throttling 導致 GC 暫停暴增** | cgroup CPU quota 被耗盡時，OS 暫停 container | GC STW 從正常 10ms 暴增到數百毫秒甚至數秒 |
| 38.3 | **`Environment.ProcessorCount` 返回宿主機核心數** | .NET Core 3.1 未正確讀取 cgroup CPU 限制 | ThreadPool 線程數設太大 → context switch 爆炸 |
| 38.4 | **Ephemeral Filesystem** | Container 重啟後 writable layer 清空 | 寫在 container 內的 log / temp / 資料檔案全部消失 |
| 38.5 | **時鐘不同步** | Container 和宿主機的時間不同、NTP 設定不一致 | Token 過期判斷錯誤、日誌時間混亂、定時任務偏移 |
| 38.6 | **Docker 網路 MTU 不匹配** | Docker bridge 預設 MTU 1500，但底層網路可能 < 1500（如 VPN、VXLAN overlay = 1450） | 大封包被靜默丟棄 → TCP 重傳暴增 → 連線超時 |
| 38.7 | **DNS 解析走 Docker 內建 DNS (127.0.0.11)** | 短暫的 DNS 查詢失敗 | 容器啟動初期連不到其他服務 |
| 38.8 | **Container 內 `ulimit` 限制** | 預設 `nofile` (open file descriptors) 可能太低 | 連線數或檔案操作達到上限 → `SocketException` / `IOException` |
| 38.9 | **Volume mount 權限問題** | 宿主機檔案 UID/GID ≠ Container 內 user | `UnauthorizedAccessException` 讀寫設定檔/資料檔 |
| 38.10 | **Image layer 快取導致舊代碼** | Docker build 快取了舊的 COPY 層 | 部署了看似新版實際是舊版的程式碼 |
| 38.11 | **Health check 設定不當** | check interval 太短或 timeout 太短 | 正常啟動中的 container 被判定不健康 → 被 orchestrator 反覆殺掉重建 |
| 38.12 | **無 init process (PID 1 問題)** | 應用直接跑在 PID 1，不收割殭屍子 Process | 殭屍 Process 累積，最終用完 PID 空間 |

---

## 39. 快取專題

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 39.1 | **Cache Stampede (驚群效應)** | 熱門 key 過期 → 瞬間 N 個請求同時穿透到 DB | DB 被 N 倍流量打爆 |
| 39.2 | **Cache Penetration (穿透)** | 查詢不存在的 key → 每次都穿透到 DB | DB 被「查不存在資料」的請求打爆 |
| 39.3 | **Cache Avalanche (雪崩)** | 大量 key 同時過期 | 同一瞬間所有請求穿透到 DB |
| 39.4 | **Cache Poisoning (污染)** | 錯誤資料被存入快取 | 所有後續讀取都拿到錯誤資料，直到 TTL 過期 |
| 39.5 | **Cold Start (冷啟動)** | Server 重啟後快取為空 | 全部請求直接打 DB → DB 過載 → Server 再崩 → 惡性循環 |
| 39.6 | **Cache-Aside 雙寫不一致** | 先更新 DB 再刪快取，中間有讀取進來 | 讀取拿到舊快取，快取被重建為舊值 |
| 39.7 | **快取 key 碰撞** | 不同資料共用了相同 key（如 `player_123` 同時代表兩種資料） | 讀到錯誤型別的資料 |
| 39.8 | **序列化的快取資料版本不匹配** | 修改了快取物件的結構（加減欄位）後讀舊資料 | 反序列化失敗或欄位錯位 |
| 39.9 | **快取記憶體無上限** | `Dictionary` 當快取但永遠不驅逐 | 記憶體持續增長 → OOM |
| 39.10 | **TTL 設為 0 或負數** | 配置錯誤 | 快取立即過期（等於沒快取）或行為未定義 |
| 39.11 | **快取讀取當作事實來源** | 業務邏輯依賴快取資料做判斷，不回查 DB | 快取過期/失效後邏輯錯誤 |
| 39.12 | **分散式快取網路分區** | Redis / Memcached 與應用之間網路斷開 | 是 fallback 到 DB 還是直接報錯？大部分沒處理 |

---

## 40. 背壓與流量控制 (Backpressure)

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 40.1 | **無界生產者佇列** | 封包接收速度 > 處理速度，佇列無限增長 | 記憶體暴漲 → OOM |
| 40.2 | **TCP 接收緩衝區堆積** | 應用層處理慢，OS TCP 接收緩衝滿了 | TCP window 降為 0 → 對端阻塞 → 影響其他連線（如果共用 thread） |
| 40.3 | **級聯失敗 (Cascading Failure)** | A 慢了 → B 等 A → B 也慢了 → C 等 B → 全部一起掛 | 整個叢集雪崩 |
| 40.4 | **無斷路器 (Circuit Breaker)** | 下游服務掛了仍持續發請求 | 執行緒/連線全卡在等回應，上游也掛 |
| 40.5 | **重試風暴 (Retry Storm)** | 失敗後立即重試、無 exponential backoff | 下游已經過載 → 重試加重負載 → 永遠恢復不了 |
| 40.6 | **同步呼叫鏈過長** | A 同步呼叫 B 呼叫 C 呼叫 D | 延遲累加，最外層超時但內層仍在跑（資源浪費） |
| 40.7 | **無速率限制的內部 API** | 伺服器間呼叫不做 rate limit | 一個有 bug 的 Server 可以打垮其他 Server |
| 40.8 | **Send buffer 堆積** | 對端讀取慢，Server 的 send queue 持續增長 | 單一慢 Client 佔用大量 Server 記憶體 |
| 40.9 | **全量同步觸發洪水** | 登入/重連時一次發送所有需要同步的資料 | 瞬間頻寬暴衝，後續封包被延遲 |
| 40.10 | **無優先級的封包佇列** | 心跳封包和巨大的場景同步封包排同一個佇列 | 心跳被延遲 → 誤判斷線 → 斷線重連 → 又觸發全量同步 → 惡性循環 |

---

## 41. 資料持久化與崩潰恢復

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 41.1 | **Partial Write (部分寫入)** | 寫入途中斷電或 process crash | 檔案/資料只寫了一半 → 下次讀取損壞 |
| 41.2 | **Write Ordering 不保證** | OS 或磁碟可能重排寫入順序 | 先寫的資料可能後落盤，中間斷電導致不一致 |
| 41.3 | **未 fsync 就認為成功** | `FileStream.Write` 只寫到 OS buffer，未 `Flush(true)` | OS crash → buffer 中的資料遺失（但應用認為已寫入） |
| 41.4 | **無 Write-Ahead Log (WAL)** | 直接修改資料檔案 | crash 後無法得知哪些操作已完成、哪些只做了一半 |
| 41.5 | **Checkpoint 間隔過長** | 記憶體快取 30 分鐘才寫回 DB 一次 | Crash 損失最多 30 分鐘的玩家進度 |
| 41.6 | **備份和運行同時進行** | 備份讀取到寫入一半的資料 | 備份檔案本身就是損壞的 |
| 41.7 | **無 Checksum 驗證** | 讀取資料時不驗證完整性 | 磁碟位元翻轉 (bit rot) 造成靜默損壞 |
| 41.8 | **自動重試寫入但無冪等** | 寫入 timeout → 重試 → 實際上第一次已成功 | 資料被寫入兩次（如金幣加兩次） |
| 41.9 | **DB 主從延遲讀取** | 寫入主庫後立即從從庫讀 | 讀到舊資料 → 業務邏輯認為寫入失敗 → 重複操作 |
| 41.10 | **Schema migration 無回滾** | ALTER TABLE 失敗但只做了一半 | DB 卡在不一致狀態 |
| 41.11 | **大量玩家同時存檔 (關服潮)** | 關服時所有玩家同時觸發存檔 | DB 瞬間寫入壓力爆表 → 部分存檔失敗 |

---

## 42. 依賴管理 (NuGet / DLL)

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 42.1 | **鑽石依賴 (Diamond Dependency)** | A 依賴 B 1.0 和 C 2.0，B 和 C 都依賴 D 但要求不同版本 | 編譯可能過但 runtime `MissingMethodException` |
| 42.2 | **Transitive 版本衝突** | 間接依賴的版本被 NuGet 自動解析到不相容版本 | 同上，但更難查因為不是直接引用 |
| 42.3 | **Deprecated API 被移除** | 更新套件後發現某個方法不見了 | `MissingMethodException` / 編譯失敗 |
| 42.4 | **Binding Redirect 不一致** | .NET Framework 殘留問題；.NET Core 少見但 Assembly 載入仍可能衝突 | `FileLoadException` |
| 42.5 | **NuGet 套件含已知 CVE** | 使用了有安全漏洞的版本但不知道 | 攻擊者利用已知漏洞 |
| 42.6 | **套件被 typosquatting** | 安裝了名稱相似的惡意套件 | Supply chain attack → RCE |
| 42.7 | **Lock file 未提交** | `packages.lock.json` 沒進版控 | 不同機器 `dotnet restore` 可能解析到不同版本 |
| 42.8 | **浮動版本 `*`** | `.csproj` 中用了 `Version="1.*"` | 每次 restore 可能拿到不同的 minor/patch 版本 |
| 42.9 | **Private feed 失效** | 企業內部 NuGet feed 掛了 | CI/CD 無法 restore → build 失敗 |
| 42.10 | **Platform-specific 套件** | NuGet 套件只有 linux-x64 runtime，沒有 win-x64 | 開發時正常（有 managed fallback），部署時效能劇降或直接失敗 |

---

## 43. 第三方函式庫陷阱

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 43.1 | **Callback 在非預期 Thread** | 第三方 SDK 的回呼在 ThreadPool thread 或自建 thread 上 | 回呼中存取主執行緒資料 → race condition |
| 43.2 | **全域狀態污染** | 第三方函式庫修改了 `ServicePointManager`、`JsonSerializerSettings` 等全域設定 | 影響整個 process 的其他功能 |
| 43.3 | **內部執行緒未關閉** | 第三方函式庫 Dispose 後仍有背景 thread 在跑 | Process 無法正常退出、資源洩漏 |
| 43.4 | **記憶體洩漏在第三方中** | 第三方的 static cache 或 event handler 洩漏 | 難以追蹤（profiler 看到洩漏在第三方 DLL 中） |
| 43.5 | **版本鎖定** | 第三方函式庫依賴特定版本的其他套件 | 你的專案無法升級該共同依賴 |
| 43.6 | **Undocumented Behavior** | 文件沒寫但實際上方法不是 thread-safe / 有 side effect | 在特定條件下才出問題 |
| 43.7 | **棄坑 (Abandoned)** | 函式庫作者不再維護 | Bug 無人修、安全漏洞無人補 |
| 43.8 | **License 陷阱** | LGPL / GPL / AGPL 函式庫被引入商業專案 | 法律風險 |
| 43.9 | **初始化順序要求** | 第三方函式庫要求在某些操作前先呼叫 `Init()` | 忘記呼叫 → 隱性錯誤或 `InvalidOperationException` |
| 43.10 | **不同 SDK 搶佔同一資源** | 兩個 SDK 都嘗試 bind 同一個 port 或設同一個 global handler | `AddressAlreadyInUseException` 或互相覆蓋 handler |

---

## 44. 加密與密碼學深度

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 44.1 | **弱 Hash 算法做安全用途** | MD5 / SHA1 用於密碼 hash 或數位簽章 | 碰撞攻擊可行 → 偽造簽章/密碼 |
| 44.2 | **ECB 模式加密** | AES-ECB 相同明文產生相同密文 | 模式可辨識 → 洩漏資訊 |
| 44.3 | **IV / Nonce 重用** | 同一個 Key + 同一個 IV 加密不同明文 | GCM 模式下直接洩漏 key；CBC 模式下洩漏明文差異 |
| 44.4 | **Padding Oracle Attack** | 錯誤的 padding 返回不同的錯誤訊息 | 逐 byte 解密（不需要 key） |
| 44.5 | **Key 寫死在原始碼** | `const string KEY = "MySecretKey123"` | 反編譯 DLL 就能拿到 key |
| 44.6 | **Key Rotation 不做** | 同一把 key 用了數年 | 一旦 key 洩漏，所有歷史資料都可解密 |
| 44.7 | **HMAC vs Hash 混淆** | 用 `SHA256(message + key)` 而非 `HMAC-SHA256(key, message)` | 長度擴展攻擊 (Length Extension Attack) |
| 44.8 | **Random 用於安全場景** | `System.Random` 產生 token / session ID | 種子可預測 → token 可預測 |
| 44.9 | **TLS 版本過低** | 允許 TLS 1.0 / 1.1 | 已知漏洞（POODLE, BEAST 等）|
| 44.10 | **憑證驗證被關閉** | `ServerCertificateCustomValidationCallback = (_, _, _, _) => true` | 中間人攻擊 (MITM) 可任意替換憑證 |
| 44.11 | **加密資料的 Metadata 洩漏** | 密文長度暴露明文長度 | 某些場景可推斷內容（如加密的選項只有幾種固定長度） |
| 44.12 | **dispose CryptoStream 忘記 FlushFinalBlock** | 最後一個 block 沒被寫出 | 解密時報 `CryptographicException: Padding is invalid` |

---

## 45. 網路拓撲與負載均衡

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 45.1 | **Session Affinity 失效** | 負載均衡器把同一玩家的封包分到不同 Server | 狀態不一致（A Server 不知道 B Server 上的操作） |
| 45.2 | **Health Check 誤判 (假陽性)** | Check 端點正常但業務邏輯已死鎖 | LB 繼續送流量到壞掉的 Server |
| 45.3 | **Health Check 誤判 (假陰性)** | Server 啟動中但 health check 已開始 → 被判不健康 | Container 被 orchestrator 殺掉重建 → 永遠啟動不完 |
| 45.4 | **Connection Draining 太短** | 摘除 Server 時只等 5 秒，但有些請求要 30 秒 | 正在進行的操作被中斷 |
| 45.5 | **Thundering Herd on Reconnect** | 斷網恢復後所有 Client 同時重連 | Server 承受 10 倍正常 TPS → 過載崩潰 → 再次斷線 → 無限循環 |
| 45.6 | **跨機房延遲未考慮** | 伺服器間通訊假設延遲 < 1ms，實際跨機房 30-100ms | 鎖等待超時、同步操作延遲暴增 |
| 45.7 | **單一 LB 是單點故障** | 負載均衡器本身掛了 | 全部流量中斷 |
| 45.8 | **LB 的 TCP timeout 與 Server 不匹配** | LB 的 idle timeout 比 Server 的 keep-alive 短 | LB 默默關閉連線，Server 不知道 → 下次 Send 才發現 |
| 45.9 | **NAT 閘道端口耗盡** | 大量對外連線通過同一個 NAT | SNAT port 耗盡 → 新連線建立失敗 |
| 45.10 | **L4 vs L7 選錯** | 遊戲用 TCP 長連線但 LB 配成 L7 HTTP | LB 嘗試解析非 HTTP 的 TCP 流量 → 連線被 reset |

---

## 46. 升級與遷移風險

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 46.1 | **Runtime 行為靜默改變** | .NET minor version 修改了某個 API 的預設行為 | 程式碼沒改但行為變了（如排序穩定性、float 精度） |
| 46.2 | **DB Schema Migration 失敗回滾** | ALTER TABLE 執行到一半超時 | 表結構處於中間狀態——既不是舊的也不是新的 |
| 46.3 | **新舊版本共存 (Rolling Update)** | 部分 Server 已更新，部分還是舊版 | 新版寫的資料格式舊版讀不懂 → 異常或資料損壞 |
| 46.4 | **Proto / 封包格式不向後相容** | 刪除了舊欄位或改了 field number | 舊 Client 連新 Server → 反序列化錯誤 |
| 46.5 | **資料遷移腳本無冪等性** | 跑兩次 migration → 資料重複 | 金幣加倍、物品複製 |
| 46.6 | **Feature Flag 殘留** | 上線後 flag 永遠不清理 | 程式碼中充斥 `if (flag.Enabled)` 死路徑 |
| 46.7 | **破壞性依賴升級** | 升級 NuGet 套件但有 breaking change | 編譯過但 runtime 行為改變 |
| 46.8 | **EOL Runtime 無法修補** | .NET Core 3.1 已 EOL，發現安全漏洞 | 沒有官方補丁，只能自行 workaround 或承受風險 |
| 46.9 | **向前相容遺忘** | 新版增加了欄位但沒考慮老資料缺少該欄位 | 讀取老資料時 `NullReferenceException` 或 default 值導致邏輯錯 |
| 46.10 | **測試環境 vs 生產環境差異** | 測試環境用 SQLite，生產用 MySQL | 測試通過但生產爆炸（SQL 方言差異、型別差異） |

---

## 47. 人為操作失誤 (Operational Error)

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 47.1 | **重啟錯的 Server** | SSH 到錯誤的機器執行重啟命令 | 正在服務的 Server 被中斷 |
| 47.2 | **Config 推到錯的環境** | 把開發環境的設定部署到生產 | 生產 Server 連到開發 DB |
| 47.3 | **忘記執行 DB Migration** | 部署了新代碼但忘記跑 schema migration | 程式碼預期的欄位/表不存在 |
| 47.4 | **維護公告沒發就開服** | 維護結束後開服但沒通知玩家 | 非技術問題但影響營運 |
| 47.5 | **手動 SQL 操作失誤** | `UPDATE player SET gold = 0` 忘記加 `WHERE` | 全服玩家金幣歸零 |
| 47.6 | **Debug 代碼留在 Production** | `if (DEBUG) GrantAllItems()` 沒移除 | 條件恰好為 true → 全服送道具 |
| 47.7 | **強制終止 Process 中途** | `kill -9` 在存檔過程中 | 資料損壞 |
| 47.8 | **錯誤的回滾** | 回滾到更舊的版本而非前一版 | 引入更多問題 |
| 47.9 | **同時操作產生衝突** | 兩個維運人員同時修改同一個設定檔 | 後儲存的覆蓋先儲存的修改 |
| 47.10 | **磁碟空間未監控** | Log / Core dump 填滿磁碟 | 所有寫入操作失敗 → Server 連環崩潰 |
| 47.11 | **SSH Key / 憑證過期** | 自動化腳本用的 key 過期 | CI/CD 無法連線到 Server → 無法部署 / 無法自動重啟 |

---

## 48. 國際化與在地化深度 (i18n/L10n)

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 48.1 | **字串長度差異** | 德文/俄文比英文長 30-50%，中文/日文需要不同字體寬度 | UI 溢出、封包超長、截斷後亂碼 |
| 48.2 | **排序規則差異** | 中文按筆劃/拼音、日文按五十音、韓文按 Jamo | `StringComparer` 在不同文化下結果不同 → 排行榜順序不一致 |
| 48.3 | **RTL (Right-to-Left) 語言** | 阿拉伯文/希伯來文從右往左 | UI 排版全壞、字串拼接順序反了 |
| 48.4 | **敏感詞過濾多語系** | 中文諧音、unicode 混淆字元繞過過濾 | 髒話/政治敏感內容出現在遊戲中 |
| 48.5 | **複數形式** | 英文 1/many，俄文有 4 種複數形式，中文不分 | 「You have 1 items」這類語法錯誤 |
| 48.6 | **日期/貨幣格式** | 美國 `$1,234.56` vs 德國 `1.234,56€` vs 日本 `￥1,234` | 格式化錯誤或解析錯誤 |
| 48.7 | **字元集限制** | 玩家名稱用了 emoji、特殊 Unicode、組合字元 | DB 存不下（`utf8` vs `utf8mb4`）、封包長度計算錯誤 |
| 48.8 | **翻譯缺失 Fallback** | 某語系缺少翻譯，fallback 到空字串而非原文 | UI 顯示空白 |
| 48.9 | **硬編碼語系文字** | `SendMessage("背包已滿")` 寫死在程式碼中 | 永遠顯示中文，無法切換語言 |
| 48.10 | **時區 vs 日期邊界** | 「每日任務重置」對不同時區的玩家意義不同 | UTC+9 的玩家和 UTC-5 的玩家的「每日」差 14 小時 |

---

## 49. 熱更新 / 動態載入

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 49.1 | **企劃表替換的 Race Condition** | 正在讀取舊表的程式碼 vs 正在替換新表的執行緒 | 讀到半新半舊的資料 |
| 49.2 | **新表格式不相容** | 新增了必填欄位但舊邏輯不知道 | `IndexOutOfRangeException` 或讀到 default 值 |
| 49.3 | **Lua / 腳本引擎沙箱逃逸** | 腳本呼叫了不該呼叫的 .NET 方法 | 任意程式碼執行 |
| 49.4 | **腳本無限迴圈** | 企劃寫的腳本有 bug → 無限迴圈 | 遊戲主執行緒卡死 |
| 49.5 | **腳本記憶體洩漏** | 腳本中建立的物件未被 GC（因為腳本引擎持有引用） | 記憶體持續增長 |
| 49.6 | **熱更後舊引用殘留** | 舊版 Assembly/Class 的實例仍在記憶體中被引用 | 新舊邏輯同時存在，行為不可預測 |
| 49.7 | **版本號不一致** | Client 拿到新表但 Server 還是舊表（或反之） | 資料不匹配 → 邏輯錯亂 |
| 49.8 | **熱更頻率過高** | 每分鐘都熱更 → 每次都有短暫的不一致窗口 | 不一致窗口累積，玩家體驗不穩定 |
| 49.9 | **回滾困難** | 熱更後發現問題但沒有保留上一版 | 只能再次熱更修正版或重啟 |
| 49.10 | **AssemblyLoadContext 洩漏** | 動態載入 Assembly 但 ALC 被靜態引用卡住 | 舊 Assembly 永遠不卸載 → 記憶體洩漏 |

---

## 50. 分散式系統基本問題

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 50.1 | **時鐘偏移 (Clock Skew)** | 不同 Server 的系統時間差異數秒到數分鐘 | 基於時間的判斷（如 Token 過期、活動開放）各 Server 不一致 |
| 50.2 | **Split Brain** | 網路分區導致叢集分裂成兩半，各自以為自己是主 | 雙主寫入 → 資料衝突不可調解 |
| 50.3 | **CAP 取捨未明確** | 系統設計時沒想清楚要犧牲哪一個 | 在網路分區時行為不可預測 |
| 50.4 | **Idempotency 未保證** | 同一請求被投遞兩次，handler 沒有冪等處理 | 操作被執行兩次（扣款兩次、發道具兩次） |
| 50.5 | **消息亂序** | 訊息佇列不保證順序 | 先收到「裝備穿上」後收到「裝備獲得」→ 邏輯錯亂 |
| 50.6 | **消息重複投遞** | At-least-once 語義下，消費者 ack 失敗 → 重投 | 同 50.4 |
| 50.7 | **分散式事務的兩階段提交 (2PC) 卡住** | Coordinator 在 Phase 2 崩潰 | Participant 永遠阻塞等待 Commit/Rollback 指令 |
| 50.8 | **最終一致性窗口過長** | 異步同步機制延遲數秒到數分鐘 | 玩家看到過期資料做了錯誤操作 |
| 50.9 | **網路分區偵測延遲** | Heartbeat interval 30 秒 → 分區後 30 秒才發現 | 30 秒內兩半叢集各自運作，產生不一致資料 |
| 50.10 | **Quorum 設定錯誤** | 3 節點要求 quorum=2，但 2 個同時掛 | 系統不可用（嚴格模式）或資料遺失（寬鬆模式） |
| 50.11 | **Exactly-once 的幻覺** | 系統聲稱 exactly-once 但實際只是 at-least-once + dedup | Dedup 機制的 TTL / 容量不足時仍會重複 |
| 50.12 | **FLP 不可能定理被忽略** | 異步分散式系統中不可能同時保證 Safety 和 Liveness | 在極端情況下系統行為出乎設計者預期 |

---

## Part 3 統計摘要

| 分類 | 項目數 |
|------|--------|
| 37. Process 生命週期與信號處理 | 12 |
| 38. Container / Docker 特有 | 12 |
| 39. 快取專題 | 12 |
| 40. 背壓與流量控制 | 10 |
| 41. 資料持久化與崩潰恢復 | 11 |
| 42. 依賴管理 | 10 |
| 43. 第三方函式庫陷阱 | 10 |
| 44. 加密與密碼學深度 | 12 |
| 45. 網路拓撲與負載均衡 | 10 |
| 46. 升級與遷移風險 | 10 |
| 47. 人為操作失誤 | 11 |
| 48. 國際化與在地化深度 | 10 |
| 49. 熱更新 / 動態載入 | 10 |
| 50. 分散式系統基本問題 | 12 |
| **Part 3 小計** | **~152 項** |

---
---

# Part 4: 既有主題深度擴充

> Part 1-2 已涵蓋但深度不足的子題，補充容易被忽略的細節。

---

## 目錄（Part 4）

51. [TCP 連線深度補充](#51-tcp-連線深度補充)
52. [位元操作與二進位細節](#52-位元操作與二進位細節)
53. [DDoS 與網路攻擊深度](#53-ddos-與網路攻擊深度)
54. [Log 與可觀測性深度](#54-log-與可觀測性深度)
55. [GC 調校與診斷深度](#55-gc-調校與診斷深度)
56. [Protobuf 實戰深度補充](#56-protobuf-實戰深度補充)

---

## 51. TCP 連線深度補充

> 擴充 Part 1 §5.1，補充 Server 開發中容易忽略的 socket 層細節。

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 51.1 | **Keep-Alive 預設 2 小時** | 系統預設 `tcp_keepalive_time = 7200秒`，太長 | 半開連線 2 小時後才被偵測到 → 資源白白佔用 |
| 51.2 | **SO_LINGER 錯用** | 設 `SO_LINGER = 0` → Close 時直接 RST，不走四次揮手 | 對端收到 RST，send buffer 中未發送的資料遺失 |
| 51.3 | **Socket Send/Receive Buffer 太小** | 預設 buffer 不夠大 | 高吞吐場景下丟包或延遲 |
| 51.4 | **Socket Send/Receive Buffer 太大** | 設成 MB 等級 | 1000 連線 × 2MB × 2(收發) = 4GB 光 buffer 就吃掉記憶體 |
| 51.5 | **TCP_NODELAY 忘記設** | Nagle 算法合併小封包 | 遊戲操作延遲 40-200ms（Part 1 5.1.7 的具體修復） |
| 51.6 | **RST 後再 Send** | 對端已 RST 但 Server 還在送 | `SocketException: Connection reset by peer` |
| 51.7 | **SocketAsyncEventArgs 池化不足** | 高併發時 pool 用完要臨時 new | new SAEA 有 kernel 開銷 → 延遲尖峰 |
| 51.8 | **Receive 回傳 partial data** | 一次 Receive 可能只拿到半個封包 | 如果沒有正確的拼包邏輯 → 解析錯誤 |
| 51.9 | **AcceptAsync 雪崩** | 大量連線同時到達，Accept 回呼互相搶佔 | 延遲暴增或部分連線 timeout |
| 51.10 | **IPv4 / IPv6 Dual Stack 設定** | 只 bind IPv4 但 Client 透過 IPv6 連線（或反之） | 連線被拒 |
| 51.11 | **Port Exhaustion (Outbound)** | Server 作為 Client 連其他服務時，本機 ephemeral port 用完 | `SocketException: Cannot assign requested address` |

---

## 52. 位元操作與二進位細節

> 擴充 Part 1 §9.10，補充封包解析和 Flag 操作中常見的位元操作陷阱。

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 52.1 | **Sign Extension (符號擴展)** | `byte b = 0xFF; int i = (int)(sbyte)b;` → i = -1 而非 255 | 封包解析時數值突然變負 |
| 52.2 | **Unsigned / Signed 混算** | `uint a = 5; int b = -1; if (a > b)` → false（b 被隱式轉 uint 變超大正數） | 比較結果反直覺 |
| 52.3 | **Big-Endian 手動拆解錯誤** | 網路位元組序 (Big-Endian) 和 x86 (Little-Endian) 搞混 | 數值完全錯誤（0x01020304 讀成 0x04030201） |
| 52.4 | **BitConverter 的 Endianness** | `BitConverter.IsLittleEndian` 因平台而異 | 同樣程式碼在 ARM Big-Endian 上行為不同 |
| 52.5 | **位移溢出無警告** | `byte b = 1; b <<= 8;` → b = 0 | 位元靜默溢出，flag 消失 |
| 52.6 | **& 和 && 混用** | `if (flags & FLAG_A == FLAG_A)` → 運算子優先級：先算 `==` | 條件永遠為 true 或 false（應寫 `(flags & FLAG_A) == FLAG_A`） |
| 52.7 | **Enum Flag 值非 2 的冪次** | `Flag1 = 1, Flag2 = 2, Flag3 = 3`（3 不是 2 的冪） | `Flag3` 等於 `Flag1 | Flag2`，位元運算邏輯全亂 |
| 52.8 | **位元欄位跨 Byte 邊界** | 手動打包 bit field 時跨越了 byte/int 邊界 | 讀寫偏移一個 bit → 後續所有欄位全錯 |
| 52.9 | **二補數表示法陷阱** | `int.MinValue` 取負值（`-int.MinValue`）仍等於 `int.MinValue` | 溢位（因為 `|int.MinValue| > int.MaxValue`） |
| 52.10 | **浮點數的位元表示** | 將 float 的 bit pattern 直接當 int 使用（如 `*(int*)&f`） | 在不同平台上 NaN 的 bit pattern 可能不同 |

---

## 53. DDoS 與網路攻擊深度

> 擴充 Part 1 §17.3，從「速率限制」擴展到完整的 Server 面對攻擊的場景。

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 53.1 | **SYN Flood** | 大量偽造來源 IP 的 SYN 封包 | Server 的 SYN Queue 填滿 → 正常連線也建不了 |
| 53.2 | **Slowloris** | 建立連線後極慢地發送 HTTP header（每 10 秒發一個 byte） | 連線槽被佔滿但每條只用極少頻寬 |
| 53.3 | **Amplification Attack** | 利用 Server 的小請求產生大回應（如 DNS 放大） | Server 出口頻寬被打滿 |
| 53.4 | **Application Layer DDoS** | 發送合法但昂貴的請求（如「搜尋所有拍賣行物品」） | 繞過 IP 級別的防護，消耗 Server CPU/DB |
| 53.5 | **Connection Exhaustion** | 建立大量 TCP 連線但不發資料 | 檔案描述符 / 記憶體 耗盡 |
| 53.6 | **Payload of Death** | 特殊構造的封包觸發 Server bug（如 crash、無限迴圈） | 單一封包就能癱瘓 Server |
| 53.7 | **Hash Collision DoS (HashDoS)** | 大量碰撞的 key 送入 Dictionary | Dictionary 退化為 O(n) → CPU 100% |
| 53.8 | **Regex DoS (ReDoS)** | 惡意輸入觸發正則回溯爆炸 | 單一請求佔用 CPU 數分鐘 |
| 53.9 | **Compression Bomb (Zip Bomb)** | 壓縮後極小的封包解壓後 GB 級 | 解壓時 OOM |
| 53.10 | **Bot 大量建立帳號** | 無 CAPTCHA / 無頻率限制的註冊 API | DB 灌水、遊戲生態被破壞 |

---

## 54. Log 與可觀測性深度

> 擴充 Part 1 §22，從「Log 壞味道」擴展到完整的可觀測性問題。

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 54.1 | **無 Correlation ID** | 跨 Server 的操作沒有統一追蹤 ID | 問題發生時無法串聯 MapServer → DbServer → PlayerDbServer 的日誌 |
| 54.2 | **無 Structured Logging** | 純文字 log `"Player 123 bought item 456"` | 無法 query「所有 item 456 的購買記錄」 |
| 54.3 | **Log Level 設錯** | 生產環境開了 Debug level | 日誌量暴增 100 倍 → 磁碟滿 + I/O 拖慢主迴圈 |
| 54.4 | **缺少 Metrics 輸出** | 沒有暴露記憶體、連線數、封包延遲、GC 暫停等指標 | 無法做 capacity planning，問題只能事後追查 |
| 54.5 | **缺少 Distributed Tracing** | 無法視覺化一次操作在多個服務間的流轉 | 延遲問題不知道卡在哪個服務 |
| 54.6 | **Alert 疲勞** | 告警設太敏感，每天上百條 | 維運開始忽略告警 → 真正的嚴重問題被淹沒 |
| 54.7 | **日誌和指標分離** | Log 存一個系統，Metrics 存另一個，無法交叉查詢 | 看到 CPU 飆高但不知道是哪個操作造成的 |
| 54.8 | **無法動態調整 Log Level** | 想開 Debug 就得重啟 Server | 重啟後 bug 現場消失 |
| 54.9 | **Audit Trail 缺失** | GM 操作、設定變更沒有記錄 | 無法追溯「誰在什麼時候做了什麼」 |
| 54.10 | **Sampling 策略不當** | 追蹤 100% 的請求 → 資料量爆炸；或追蹤 0.1% → 問題剛好不在樣本中 | 空間浪費 或 無法重現問題 |

---

## 55. GC 調校與診斷深度

> 擴充 Part 1 §4.2，補充 .NET GC 調校與實戰診斷的具體陷阱。

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 55.1 | **Server GC vs Workstation GC 選錯** | 遊戲 Server 用了 Workstation GC（預設） | Workstation GC 更頻繁且在使用者 thread 上暫停 → 遊戲卡頓 |
| 55.2 | **`GCSettings.LatencyMode` 未調** | 預設 `Interactive`，但遊戲需要 `SustainedLowLatency` | GC 暫停時間不可控 |
| 55.3 | **手動 `GC.Collect()` 在錯誤時機** | 在遊戲主迴圈中呼叫 `GC.Collect()` | 觸發 Full GC → 全部 thread 暫停數十到數百毫秒 |
| 55.4 | **LOH Compaction 未設定** | .NET Core 3.x 的 LOH 預設不 compact | LOH 碎片化持續累積（Part 1 4.2.2 的修復方式：`GCSettings.LargeObjectHeapCompactionMode`） |
| 55.5 | **記憶體壓力通知未處理** | `GC.RegisterForFullGCNotification` 或 `MemoryCache` 的 size limit 未設 | 記憶體慢慢增長但無預警，直到 OOM |
| 55.6 | **Finalizer Queue 監控缺失** | 不知道 Finalizer queue 積壓了多少物件 | Finalizer thread 追不上 → 記憶體持續增長但看不到原因 |
| 55.7 | **Gen2 GC 頻率監控缺失** | 不知道 Gen2 GC 每分鐘觸發幾次 | GC 壓力已經很大但沒有 metrics 顯示 |
| 55.8 | **Dispose 但不 null 引用** | `Dispose()` 後物件仍被 GC Root 引用 → 無法回收 | 邏輯上已釋放但記憶體未釋放 |
| 55.9 | **GC.AddMemoryPressure 遺忘** | 持有大量 native 記憶體但 GC 不知道 | GC 認為記憶體充足不回收 → native OOM |
| 55.10 | **Container 環境下 GC Heap 限制** | `GCHeapHardLimit` 未設定或設太大 | 超出 container memory limit → OOM Killer |

---

## 56. Protobuf 實戰深度補充

> 擴充 Part 1 §7.1，補充遊戲伺服器中 Protobuf 的實際使用陷阱。

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 56.1 | **Field Number 重用** | 刪了舊欄位後把它的 number 給新欄位 | 舊資料的舊欄位被解析成新欄位 → 資料損壞 |
| 56.2 | **Map 欄位的序列化不確定性** | `map<k,v>` 的序列化順序不保證 | 同一資料序列化兩次得到不同 bytes → hash/checksum 比對失敗 |
| 56.3 | **Enum 第一個值必須是 0** | proto3 要求 enum 第一個值 = 0 | 不遵守則預設值不是「第一個成員」→ 邏輯混亂 |
| 56.4 | **Message 嵌套過深** | 5+ 層巢狀 Message | 序列化/反序列化效能差 + 程式碼可讀性差 |
| 56.5 | **Large repeated bytes field** | `repeated bytes` 存放大量小 byte array | 每個 bytes 元素都有 tag + length 前綴 → overhead 可能 > 資料本身 |
| 56.6 | **Proto 檔案 import 循環** | A.proto import B.proto import A.proto | protoc 編譯失敗或生成的 C# 碼有循環依賴 |
| 56.7 | **Proto message 當 DB 欄位** | 整個 proto 序列化後存 DB 的 BLOB 欄位 | 無法 SQL query 內部欄位、schema 遷移極困難 |
| 56.8 | **MergeFrom 的語義** | `MergeFrom` 對 repeated 欄位是 append 不是 replace | 多次 merge → 列表膨脹 |
| 56.9 | **Proto3 optional 的回歸** | proto3 後期加回 `optional`，但行為和 proto2 不完全一樣 | field presence 語義混亂 |
| 56.10 | **跨語言 Proto 精度差異** | C# 的 double 和 JavaScript 的 Number 精度不完全一致 | 跨端數值微差異（如排行榜分數不一致） |

---

## Part 4 統計摘要

| 分類 | 項目數 |
|------|--------|
| 51. TCP 連線深度補充 | 11 |
| 52. 位元操作與二進位細節 | 10 |
| 53. DDoS 與網路攻擊深度 | 10 |
| 54. Log 與可觀測性深度 | 10 |
| 55. GC 調校與診斷深度 | 10 |
| 56. Protobuf 實戰深度補充 | 10 |
| **Part 4 小計** | **~61 項** |

---
---

# 全文件總計

| 部分 | 說明 | 項目數 |
|------|------|--------|
| Part 1 | 異常危險狀態 (§1-§22) | ~227 |
| Part 2 | 壞味道 (§23-§36) | ~151 |
| Part 3 | 確定缺漏的獨立主題 (§37-§50) | ~152 |
| Part 4 | 既有主題深度擴充 (§51-§56) | ~61 |
| **合計** | **56 個分類** | **~591 項** |

---

## 後續步驟

以此 591 項為錨點清單，逐項對照 `sgi_server` 專案程式碼進行排查：
1. 依風險等級（崩潰 > 資料損壞 > 效能 > 邏輯錯誤 > 維護成本）排序
2. 對每一項在專案中搜尋實際出現的 pattern
3. 產出專案特定的風險報告與修復建議

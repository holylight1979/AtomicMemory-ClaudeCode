# Unity C# 遊戲客戶端 全面異常危險狀態清單＋壞味道全集（通用知識庫）

> 目標：窮舉 Unity 遊戲客戶端 C# 程式碼中，所有已知可能引發異常的危險狀態與壞味道。
> 與《全面CSharpServer危險彙整》互補：**C# 語言層／執行緒／集合／async／GC 通論／序列化通論／Null／IDisposable／反射通論，Server 篇已有，本篇不重複**；只收「在 Unity 裡表現不同」或「Unity 才有」的項目。
> 與本機壞味道語料庫互補：`_AIDocs/Research/code-smells/`（513 條，根索引 `00-index.md`）。Part 2 凡語料庫已有的條目只在「既有」欄指過去，不重寫；只有 Unity 引擎層、語料庫沒有的才完整寫。
> 來源：公開文獻、Unity 官方手冊與部落格、Unity 論壇／Stack Overflow 常見坑、JetBrains Rider Unity 檢查規則、HybridCLR 官方 README 與社群筆記、手遊客戶端實戰經驗。
> 標註規則：**〔官〕**＝本次查證到 Unity／廠商官方文件；**〔社〕**＝論壇、社群文章、第三方部落格（需對照自家 Unity 版本）；**未標註者＝實戰經驗或文件常識，本次未逐條查證**，使用前請對照自家 Unity 版本實測。
> 版本差異：Unity 2019 LTS 到 Unity 6 之間行為有差（增量 GC、Domain Reload 設定、Awaitable、新 Input System、Addressables 2.x 等）；條目寫現行共通行為，個別條目已註明適用範圍。

本次實際讀到的查證來源：
- Unity 手冊「Garbage collection modes」：https://docs.unity3d.com/Manual/performance-incremental-garbage-collection.html
- Unity 手冊「IL2CPP scripting restrictions」：https://docs.unity3d.com/Manual/ScriptingRestrictions.html
- Unity 手冊「Time and frame rate management」：https://docs.unity3d.com/Manual/TimeFrameManagement.html
- Addressables「Memory management」：https://docs.unity3d.com/Packages/com.unity.addressables@2.2/manual/MemoryManagement.html
- Unity 部落格「Custom == operator, should we keep it?」：https://unity.com/en/blog/engine-platform/custom-operator-should-we-keep-it
- Unity Support「Split canvas for dynamic objects」：https://support.unity.com/hc/en-us/articles/115000355466
- Unity Learn「Optimizing Unity UI」：https://learn.unity.com/tutorial/optimizing-unity-ui
- Unity 手冊「Execution Order of Event Functions」（搜尋所見多為舊版，現行版請對照）：https://docs.unity3d.com/Manual/ExecutionOrder.html
- HybridCLR：https://github.com/focus-creative-games/hybridclr （README 與社群筆記；個別限制以所用版本的官方文件為準）

---

## 目錄

**Part 1：異常危險狀態**

1. [MonoBehaviour 生命週期與執行順序](#1-monobehaviour-生命週期與執行順序)
2. [Update／FixedUpdate／Coroutine／async](#2-updatefixedupdatecoroutineasync)
3. [主執行緒獨占 API 與 Jobs／Burst](#3-主執行緒獨占-api-與-jobsburst)
4. [Unity GC 與每幀配置](#4-unity-gc-與每幀配置)
5. [Unity 序列化](#5-unity-序列化)
6. [Prefab／Scene 參照與遺失](#6-prefabscene-參照與遺失)
7. [資源載入與記憶體](#7-資源載入與記憶體)
8. [UI（UGUI／TMP／UI Toolkit）](#8-uiugui--tmp--ui-toolkit)
9. [動畫與物理](#9-動畫與物理)
10. [時間與幀率](#10-時間與幀率)
11. [浮點、決定性與隨機](#11-浮點決定性與隨機)
12. [事件、委派與單例殘留](#12-事件委派與單例殘留)
13. [IL2CPP／AOT／Code Stripping](#13-il2cppaotcode-stripping)
14. [熱更系統（ILRuntime／HybridCLR）](#14-熱更系統ilruntimehybridclr)
15. [平台與行動端](#15-平台與行動端)
16. [Editor 與 Runtime 混用](#16-editor-與-runtime-混用)
17. [存檔與本地資料](#17-存檔與本地資料)
18. [輸入](#18-輸入)
19. [多場景與場景載入](#19-多場景與場景載入)
20. [物件池與 Instantiate／Destroy](#20-物件池與-instantiatedestroy)
21. [字串與本地化](#21-字串與本地化)
22. [Shader／材質（C# 側）](#22-shader材質c-側)
23. [Debug.Log 與效能](#23-debuglog-與效能)
24. [第三方 SDK 整合](#24-第三方-sdk-整合)
25. [客戶端網路與同步](#25-客戶端網路與同步)
26. [音訊、粒子、相機](#26-音訊粒子相機)
27. [Build 與專案設定](#27-build-與專案設定)
28. [客戶端安全與防作弊](#28-客戶端安全與防作弊)

**Part 2：Unity 壞味道**（欄位：怎麼認／怎麼修／既有）

29. [MonoBehaviour 結構壞味道](#29-monobehaviour-結構壞味道)
30. [參照與依賴壞味道](#30-參照與依賴壞味道)
31. [事件與訊息壞味道](#31-事件與訊息壞味道)
32. [繼承與 Prefab 壞味道](#32-繼承與-prefab-壞味道)
33. [流程控制壞味道](#33-流程控制壞味道)
34. [魔法字串與資料壞味道](#34-魔法字串與資料壞味道)
35. [UI 架構壞味道](#35-ui-架構壞味道)
36. [資源與生命週期管理壞味道](#36-資源與生命週期管理壞味道)
37. [熱更架構壞味道](#37-熱更架構壞味道)
38. [Editor／工具／Build 壞味道](#38-editor工具build-壞味道)
39. [Unity 效能壞味道](#39-unity-效能壞味道)
40. [測試與可維護性壞味道](#40-測試與可維護性壞味道)

---
---

# Part 1：Unity 客戶端異常危險狀態

---

## 1. MonoBehaviour 生命週期與執行順序

### 1.1 初始化順序
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 1.1.1 | Awake／OnEnable 內存取別的物件 | 場景內多個物件的 Awake／OnEnable 順序不保證（只有 Script Execution Order 能在「腳本型別」層級調整） | 讀到尚未初始化的欄位 → `NullReferenceException`，偶發、換機器或換場景才爆〔官〕〔社〕 |
| 1.1.2 | Start 內依賴別人的 Start | 所有 Awake 先於所有 Start，但 Start 之間順序不保證 | 同上；只在特定載入順序出錯 |
| 1.1.3 | `Instantiate` 回傳前 Awake／OnEnable 已執行 | prefab 為 active，建立當下就同步呼叫 | 在 Instantiate「之後」才賦值的欄位，Awake 內讀不到 → 用到預設值 |
| 1.1.4 | `AddComponent` 後 Awake 立即執行 | 物件為 active 時同步呼叫 Awake／OnEnable | 想在 Awake 後才注入的參數尚未設定；Awake 內已拿 null 做事 |
| 1.1.5 | 非 active 物件的 Awake／Start 不跑 | 物件以 inactive 狀態存在，直到被 SetActive(true) | `GetComponent` 取得到元件，但元件尚未初始化；外部呼叫其方法 → NRE |
| 1.1.6 | OnEnable 先於 Start（首次） | OnEnable 內用到 Start 才建立的東西 | NRE；且每次重新啟用 OnEnable 再跑、Start 卻不再跑，初始化責任錯置 |
| 1.1.7 | Start 只執行一次 | 物件池重用物件，把「每次取出要重設」的邏輯寫在 Start | 第二次取出後狀態不重設，殘留上一次的資料 |
| 1.1.8 | MonoBehaviour 建構子／欄位初始化器呼叫 Unity API | 建構子可能在載入或序列化階段、甚至非主執行緒被呼叫 | 例外「not allowed to be called from a MonoBehaviour constructor」；或建構子被呼叫多次（反序列化重建） |
| 1.1.9 | 依賴 `OnValidate`／`Reset` 補欄位 | 這兩個只在 Editor 呼叫 | Editor 裡正常、Build 後欄位是空的 |
| 1.1.10 | `IEnumerator Start()` 內拋例外 | Start 回傳 IEnumerator 會被當 coroutine 跑 | 例外只終止該 coroutine，其後初始化全部沒跑，只有 Console 一行紅字 |

### 1.2 啟用、停用、銷毀
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 1.2.1 | `Destroy` 不是立即生效 | 物件在當幀結束才真正銷毀 | 同幀內物件仍能被 Find／GetComponent 找到、仍可能再被 Destroy 或再被使用 |
| 1.2.2 | 為了「立刻消失」改用 `DestroyImmediate` | 在 Update 或回呼中立即銷毀 | 迭代中的集合與其他腳本持有的參照瞬間失效；非 Editor 情境使用有資料損壞風險 |
| 1.2.3 | `Destroy(this)` 以為移除整個物件 | `this` 是元件不是 GameObject | 只移除腳本，物件與子物件留在場景（幽靈物件） |
| 1.2.4 | OnDestroy 內存取其他物件 | 場景卸載或父物件銷毀時，銷毀順序不定 | 取到已銷毀物件 → `MissingReferenceException` |
| 1.2.5 | OnDestroy 內建立新物件或單例 | 退出播放或場景卸載時重新建立 | Editor 留下殘留物件、"Some objects were not cleaned up"；單例在關閉時被復活 |
| 1.2.6 | `SetActive(false)` 停止所有 coroutine，且重新啟用不會續跑 | 把 coroutine 當持久狀態機 | 重新啟用後流程卡死在中途，沒有任何錯誤 |
| 1.2.7 | 只 `enabled = false` 不會停 coroutine 與 `Invoke` | 以為停用元件就停所有邏輯 | 元件「停用」後仍在跑 coroutine 與 Invoke |
| 1.2.8 | OnApplicationQuit／OnDestroy 在行動端不保證被呼叫 | 被系統殺 process、從多工清單滑掉 | 存檔寫在 OnApplicationQuit → 資料遺失（見 §15、§17） |
| 1.2.9 | 退出階段的 OnDisable／OnDestroy 又去存取單例 `Instance` | 單例 getter 找不到就 new | 退出時又建出新物件，Editor 留下殘留場景物件 |

### 1.3 偽 null（Unity 自訂 `==`）
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 1.3.1 | 對 `UnityEngine.Object` 用 `?.`、`??`、`??=` | 這些運算子不走 Unity 重載的 `==`，只做純 C# 參考檢查 | 已銷毀物件被當成存活 → `MissingReferenceException`；Rider 有專用檢查〔官〕〔社〕 |
| 1.3.2 | 用 `is null`、`is not null`、`ReferenceEquals`、`(object)x == null` 判斷 | 同上，繞過生命週期檢查 | 已銷毀物件判成非 null |
| 1.3.3 | 泛型方法內 `where T : class` 寫 `x == null` | 泛型內的 `==` 在編譯期綁成參考比較 | 傳進 Unity 物件時偽 null 判斷失效 |
| 1.3.4 | `List<GameObject>`／陣列內含已銷毀元素 | Destroy 後集合不會自動移除 | 元素變成偽 null，Count 沒變，迭代時 NRE／Missing |
| 1.3.5 | 已銷毀物件當 Dictionary key／HashSet 成員 | 條目不會自動消失 | 集合持續膨脹、持有 managed 殼；查表命中死物件 |
| 1.3.6 | coroutine／async／lambda 回呼跨幀持有 Unity 物件 | 等待期間物件被銷毀 | 回呼醒來時用的是死物件 |
| 1.3.7 | Editor 與 Build 中 `GetComponent` 找不到時的回傳不同 | Editor 回傳帶提示訊息的偽 null，Build 回傳真 null | 在 Editor 通過的 `?.` 判斷，Build 行為不同 |

### 1.4 執行順序設定
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 1.4.1 | 依賴 Script Execution Order 專案設定決定順序 | 設定存在 ProjectSettings，被他人改動或合併衝突遺失 | 順序悄悄改變，初始化隨機出錯 |
| 1.4.2 | Update 之間順序不保證 | A 讀 B 本幀還是上一幀的值不定 | 抖動、延遲一幀、跟隨類邏輯不穩 |
| 1.4.3 | 相機跟隨寫在 Update，被跟隨者在別處 Update 移動 | 順序不定 | 相機畫面抖動；應在 LateUpdate 或 Cinemachine 對應更新模式 |
| 1.4.4 | `RuntimeInitializeOnLoadMethod` 彼此順序不保證 | 多個靜態初始化方法互相依賴 | 偶發 NRE；Domain Reload 關閉時行為更難預期 |
| 1.4.5 | `SendMessage`／`BroadcastMessage` 用字串 | 以反射呼叫，找不到方法預設靜默（除非 RequireReceiver） | 改名後訊息消失而不報錯；效能差 |

---

## 2. Update／FixedUpdate／Coroutine／async

### 2.1 Update 系
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 2.1.1 | FixedUpdate 內處理 `GetKeyDown`／`GetButtonDown` | FixedUpdate 與渲染幀不同步，一幀內可能 0 次或多次 | 按鍵漏接或重複觸發 |
| 2.1.2 | Update 內改 Rigidbody 而非 FixedUpdate | 幀率不固定 | 物理結果隨幀率變動，穿牆、速度不一致（見 §9） |
| 2.1.3 | 低幀率時 FixedUpdate 一幀跑多次 | Unity 會補跑固定步進直到追上，受 `maximumDeltaTime` 限制 | 補跑本身很重 → 更慢 → 更多補跑，卡頓螺旋；超過上限時模擬時間被截斷〔官〕 |
| 2.1.4 | 高幀率時一幀 0 次 FixedUpdate | 兩次渲染幀間不足一個固定步進 | 依賴 FixedUpdate 做「每幀一次」的邏輯會漏〔官〕 |
| 2.1.5 | LateUpdate 與 Animator／IK 更新順序 | 骨骼姿勢在動畫階段後才定 | 讀到上一幀骨骼位置，附掛物件抖動 |
| 2.1.6 | Update 內拋例外 | Unity 不會停止該物件，每幀再拋一次 | Console 被灌爆、效能崩、該方法後面邏輯都不跑 |

### 2.2 Coroutine
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 2.2.1 | Coroutine 依附於啟動它的 MonoBehaviour | 物件被 Destroy 或 SetActive(false) | coroutine 靜默終止，後續步驟（解鎖 UI、回收物件）永不執行 |
| 2.2.2 | `StopCoroutine` 用錯參考 | 必須用同一個 Coroutine 參考，或與啟動時同名字串 | 停不掉，重複啟動多份 |
| 2.2.3 | 重複 `StartCoroutine` 同一流程 | 按鈕連點、事件重入 | 多份 coroutine 同時改同一狀態，結果錯亂 |
| 2.2.4 | `WaitForSeconds` 受 timeScale 影響 | timeScale = 0 時永不結束 | 暫停選單內的 coroutine 卡死；應用 `WaitForSecondsRealtime` |
| 2.2.5 | `WaitForFixedUpdate`／`WaitForEndOfFrame` 混淆 | 兩者所處階段不同 | 在錯誤階段讀寫物理或畫面（截圖必須 EndOfFrame） |
| 2.2.6 | coroutine 內的 try／catch 包不住 `yield return` | C# 限制：有 catch 的 try 區塊內不可 yield | 例外處理被迫繞道，容易漏接例外 |
| 2.2.7 | coroutine 持有 Unity 物件跨越多幀 | 等待期間物件被銷毀 | 恢復時 MissingReferenceException |
| 2.2.8 | 把 coroutine 當有限狀態機或長流程 | 狀態只存在於 IEnumerator 區域變數 | 無法序列化、無法中斷續跑、無法查目前狀態（見 §33） |

### 2.3 async／await 與 Awaitable
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 2.3.1 | `ConfigureAwait(false)` 後碰 Unity API | Unity 安裝 UnitySynchronizationContext，預設 await 後回主執行緒；`ConfigureAwait(false)` 後續跑在執行緒池 | 例外「can only be called from the main thread」 |
| 2.3.2 | `Task.Run` 內碰 Unity API | 背景執行緒 | 同上（見 §3） |
| 2.3.3 | 物件銷毀後 async 方法仍繼續 | Task 不會因 MonoBehaviour 銷毀而取消 | 醒來時存取死物件；需 `destroyCancellationToken`（Unity 2022.2+）或自行管理 |
| 2.3.4 | `async void` 方法 | 例外丟到 SynchronizationContext | 非預期時機報錯、無法 await；僅限事件處理器 |
| 2.3.5 | 未觀察的 Task 例外 | fire-and-forget 沒人 await | 錯誤被吞，或僅在 GC 時以 UnobservedTaskException 浮現 |
| 2.3.6 | 主執行緒 `.Result`／`.Wait()` 等需回主執行緒的 Task | 主執行緒被阻塞，續體要回主執行緒才能完成 | 死鎖，遊戲凍結 |
| 2.3.7 | WebGL 使用多執行緒 | WebGL 不支援執行緒 | `Task.Run`、`Thread` 失敗或退化 |
| 2.3.8 | Unity 內建 `Awaitable`（2023.1+）被重複 await 或存起來晚用 | 池化物件，只能 await 一次 | 未定義行為〔社〕 |
| 2.3.9 | `Task.Delay` 不受 timeScale 影響 | 用真實時間 | 暫停遊戲時延遲仍照走，與 coroutine 的 `WaitForSeconds` 行為不一致 |

### 2.4 AsyncOperation／UnityWebRequest
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 2.4.1 | `allowSceneActivation = false` 時進度卡在 0.9 | 等待啟用指令 | 載入條永遠不到 100%，等不到完成 |
| 2.4.2 | 未檢查 `UnityWebRequest.result` | 只檢查舊版 `isNetworkError`／`isHttpError` | 4xx／5xx 或連線失敗被當成功，使用空內容 |
| 2.4.3 | UnityWebRequest 未 `Dispose` | 其內有 native 下載緩衝與 handler | native 記憶體洩漏 |
| 2.4.4 | 大檔使用 `DownloadHandlerBuffer` | 整個檔案進記憶體 | 行動端 OOM，應用 `DownloadHandlerFile` |
| 2.4.5 | 請求回呼觸發時發起者已被銷毀 | 回呼操作死物件 | MissingReferenceException |
| 2.4.6 | `CertificateHandler` 直接回傳 true | 為了方便略過憑證驗證 | 中間人攻擊風險，上架審核被拒 |

---

## 3. 主執行緒獨占 API 與 Jobs／Burst

### 3.1 主執行緒獨占
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 3.1.1 | 背景執行緒存取 `transform`、`GameObject`、`Component` | Unity 物件屬性幾乎都是主執行緒獨占 | 例外「can only be called from the main thread」；偶爾不拋例外而直接資料損壞 |
| 3.1.2 | 背景執行緒呼叫 `Time.time`、`Random.value`、`Application.dataPath` 等 | 看似純數值，實為 native 呼叫 | 同上；需在主執行緒先讀好再傳入 |
| 3.1.3 | 在 Socket／Task 回呼直接 `Instantiate` 或改 UI | 回呼來自 IO 執行緒 | 例外或畫面不更新，常是偶發 |
| 3.1.4 | 背景執行緒建立 `Texture2D`、`Mesh`、`Material` | 這些建構是主執行緒獨占 | 例外；解法為背景準備 byte[]，主執行緒建立物件 |
| 3.1.5 | 「回主執行緒」佇列每幀全部清空 | 一幀內處理過多任務 | 單幀卡頓，需每幀預算上限 |
| 3.1.6 | 靜態建構子／靜態欄位初始化呼叫 Unity API | 可能被背景執行緒觸發類別初始化 | 例外，類別永久進入初始化失敗狀態（TypeInitializationException） |

### 3.2 回主執行緒的分派
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 3.2.1 | 自製分派器掛在場景物件上 | 場景切換時分派器被銷毀 | 之後所有回呼丟失；應 `DontDestroyOnLoad` 或注入 PlayerLoop |

### 3.3 C# Job System 與 Burst
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 3.3.1 | Job 內使用 managed 型別（class、string、List） | Burst／Job 僅支援 blittable 與 Native 容器 | 編譯錯誤，或失去 Burst 優化 |
| 3.3.2 | NativeContainer 未 `Dispose` | native 記憶體不歸 GC 管 | 記憶體洩漏；Editor 有 Leak Detection 警告 |
| 3.3.3 | 多個 Job 同時寫同一 NativeArray 無依賴 | Safety System 偵測資料競態 | Editor 拋 InvalidOperationException；Build 無檢查直接資料損壞 |
| 3.3.4 | 未 `Complete()` 就讀結果 | Job 尚未完成 | 讀到舊資料；Editor 有檢查，Build 沒有 |
| 3.3.5 | `Allocator.Temp` 容器傳給 Job 或跨幀保留 | Temp 僅限當幀、當執行緒 | 使用已失效記憶體 → 崩潰；需 `TempJob` 或 `Persistent` |
| 3.3.6 | Editor 關閉 Burst 或未標 `[BurstCompile]` | Burst 編譯只在啟用時生效 | 效能在 Editor 與 Build 差異巨大，效能測試失真 |
| 3.3.7 | Burst 內浮點行為與 Mono／IL2CPP 的 C# 不完全相同 | FastMath、不同指令集、`FloatMode` 設定 | 跨平台、跨設備結果微差，影響決定性（見 §11） |
| 3.3.8 | `NativeArray` 越界在 Build 不檢查 | 安全檢查僅 Editor／Development | Build 中越界寫入 → 隨機崩潰、記憶體損壞 |

---

## 4. Unity GC 與每幀配置

### 4.1 Unity GC 的特性（與 Server 篇 .NET GC 不同）
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 4.1.1 | Unity 的 GC 是 Boehm–Demers–Weiser，**不壓縮**，社群描述為**不分代** | Mono 與 IL2CPP 均如此 | 每次 GC 要掃整個託管堆，堆越大停頓越長；.NET「Gen0 便宜回收」的假設不成立〔官〕（不壓縮）〔社〕（不分代） |
| 4.1.2 | 不壓縮 → 記憶體碎片 | 物件不會被搬移 | 總量夠但分配失敗；堆只擴不縮，行動端 RSS 持續高位，易被系統殺〔官〕 |
| 4.1.3 | 預設為增量 GC，仍可能長停頓 | 增量模式把工作攤到多幀，分配過快或工作量大時仍會卡 | 以為開了增量就沒卡頓；CoreCLR 後端與 Web 平台不支援增量 GC〔官〕 |
| 4.1.4 | 手動 `GC.Collect()` | 想「清乾淨」 | 單次數十到數百 ms 卡頓；只應在載入畫面呼叫 |
| 4.1.5 | `GarbageCollector.GCMode = Disabled` 後沒回復 | 戰鬥中停 GC，忘了重開 | 堆無限成長 → OOM〔官〕 |
| 4.1.6 | Manual 模式下沒排程回收 | 完全自己控制 | 同上；需設定合理的觸發點與記憶體上限〔官〕 |
| 4.1.7 | Native 記憶體（Texture、Mesh、Audio）不在託管堆 | GC 看不到這些壓力 | 託管堆小但整體記憶體爆；靠 `Resources.UnloadUnusedAssets` 或顯式 Destroy 才處理 |

### 4.2 每幀配置的來源（通論條目見語料庫 H05、D03、E01、E04、E05，這裡只收 Unity 專屬）
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 4.2.1 | 每幀 `new List<T>()`／`new T[]` | 臨時集合 | 每幀垃圾，累積觸發 GC 卡頓 |
| 4.2.2 | `GetComponents<T>()`、`FindObjectsOfType<T>()`、`Physics.RaycastAll`、`Physics.OverlapSphere` | 每次回傳新陣列 | 每幀陣列配置；改用 NonAlloc 版或傳入 List 的重載 |
| 4.2.3 | `Mesh.vertices`／`.normals`／`.uv`、`Renderer.materials`、`Input.touches`、`Animator.parameters` 在迴圈內反覆讀取 | getter 每次回傳副本陣列 | 等於反覆配置大陣列（既有 H06） |
| 4.2.4 | `gameObject.tag ==` 字串比較 | `.tag` 取值會配置字串 | 每次比較配置；改用 `CompareTag`（既有 H03） |
| 4.2.5 | 每幀刷新 UI 文字（分數、計時）用字串串接或 `string.Format` | 字串不可變 | 每幀產生新字串；改為值變動才更新，或用 TMP 的 `SetText` 數值重載 |
| 4.2.6 | `foreach` 透過介面型別迭代 | `IEnumerable<T>` 轉型 box 列舉器 | 每次配置；新版編譯器對 `List<T>` 已改善，需實測自家版本（既有 H07） |
| 4.2.7 | `Camera.main` 舊版本每次 FindWithTag | 2020.2 前未快取 | 舊專案熱點；沒有 MainCamera tag 時回 null（既有 H02） |

### 4.3 查找與快取
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 4.3.1 | Update 內 `GetComponent` | 每次是 native 查找 | 數百物件時成為熱點；應在 Awake 快取（既有 H01） |
| 4.3.2 | `GameObject.Find`／`FindObjectOfType`／`FindWithTag` 在執行期 | 遍歷整個場景 | 場景越大越慢，依賴名稱或型別，改名即壞 |
| 4.3.3 | `transform.Find("A/B/C")` 階層路徑字串 | 改階層或改名 | 靜默失敗，回 null |
| 4.3.4 | Update 內 `Resources.Load`／`Instantiate` | 重工作在每幀 | 嚴重卡頓；應預載加物件池 |
| 4.3.5 | 用字串版 `animator.SetFloat("Speed", …)`、`material.SetFloat("_Color", …)` | 字串→hash 每次計算 | 熱路徑成本；預先快取 `StringToHash`／`PropertyToID`（既有 H10） |

---

## 5. Unity 序列化

### 5.1 欄位序列化規則
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 5.1.1 | `public` 欄位自動被序列化 | 以為 public 只是存取修飾詞 | 欄位值被場景／prefab 存下，覆蓋程式內的預設值；改程式預設值無效 |
| 5.1.2 | 屬性（Property）不被序列化 | Unity 只序列化欄位 | `public int Hp { get; set; }` 在 Inspector 看不到、值不保存；需 `[field: SerializeField]` |
| 5.1.3 | `[SerializeField]` 欄位改名 | 序列化資料以欄位名為鍵 | 舊 prefab／場景資料悄悄遺失，欄位回到預設；需 `[FormerlySerializedAs]` |
| 5.1.4 | `Dictionary<K,V>` 不能直接序列化 | Unity 序列化器不支援 | Inspector 看不到、值丟失；需拆成兩個 List（ISerializationCallbackReceiver） |
| 5.1.5 | 巢狀集合（`List<List<T>>`、`T[][]`）不被序列化 | 不支援 | 資料被丟失；需包一層可序列化類別 |
| 5.1.6 | 改程式預設值後舊物件沒有套用 | 已序列化的值覆蓋程式預設值 | 新增欄位預設值只對新實例有效，舊 prefab 是 0／null |
| 5.1.7 | `[HideInInspector]` 當成 `[NonSerialized]` | 前者仍然序列化只是不顯示 | 以為資料不被存，實際仍寫入 prefab，肥大與版控 diff |
| 5.1.8 | `[SerializeField]` 欄位同時被程式碼賦值 | 序列化值與執行期值混用 | 無法分辨「設計資料」或「執行期狀態」，重新載入後被覆蓋 |

### 5.2 自訂類別、多型與循環
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 5.2.1 | 序列化類別欄位不會是 null | Unity 會自動 new 預設實例 | `if (field == null)` 永遠為 false；遞迴型別造成深度警告 |
| 5.2.2 | 自身型別欄位的 `[Serializable]` 類別（遞迴結構） | 序列化器不支援參考循環 | 被展開到深度上限，載入時間與檔案大小暴增 |
| 5.2.3 | 基底類別欄位放子類別實例 | 預設按「欄位宣告型別」序列化 | 子類別獨有欄位遺失；需 `[SerializeReference]` |
| 5.2.4 | `[SerializeReference]` 的類別改名／換命名空間／搬 assembly | 序列化資料紀錄型別全名 | 載入後該欄位為 null，資料遺失；需 `[MovedFrom]` |
| 5.2.5 | `[SerializeReference]` 實例被多個欄位共用 | 序列化後保留共用 | 編輯一處影響多處，與值語意預期不符 |
| 5.2.6 | 抽象類別、介面型別欄位 | 不能直接序列化 | 欄位不出現；需 `[SerializeReference]` 或包裝 |
| 5.2.7 | `JsonUtility` 與 Inspector 序列化規則相同 | 不支援 Dictionary、多型、屬性、頂層陣列 | 解析出來資料缺漏，不報錯 |
| 5.2.8 | `JsonUtility.FromJson` 缺欄位或多欄位 | 不嚴格驗證 | 缺欄位用預設值，無警告；資料損壞靜默通過 |

### 5.3 ScriptableObject
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 5.3.1 | 執行期修改 ScriptableObject 資產 | Editor 中修改會寫回 asset；Build 中只在記憶體 | Editor 測試時資料被永久改動，Build 與 Editor 行為不一致 |
| 5.3.2 | 把 ScriptableObject 當存檔或狀態倉庫 | 以為是可寫資料庫 | Build 中重啟即重置，Editor 中汙染資產 |
| 5.3.3 | 多個物件共用同一 ScriptableObject 實例 | 共享參考 | 一處修改影響所有人；需 `Instantiate` 取得私有副本 |
| 5.3.4 | ScriptableObject 的 `OnEnable` 在 Editor 與 Build 時機不同 | Editor 在 Domain Reload、進入播放時多次呼叫 | 初始化重複或漏掉 |
| 5.3.5 | SO 內 static 欄位在 Domain Reload 關閉時殘留 | 狀態跨播放保留 | Editor 第二次播放帶著上次的資料（見 §16） |
| 5.3.6 | SO 以 Addressables／AssetBundle 打包時依賴被複製 | 不同 bundle 各自包含一份被引用資源 | 重複資源，記憶體倍增（見 §7） |

---

## 6. Prefab／Scene 參照與遺失

### 6.1 參照遺失
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 6.1.1 | Missing Script | 腳本被刪、改名、移到另一 assembly 或 GUID 變更 | 元件變 Missing，邏輯完全消失；Build 時不一定有錯誤 |
| 6.1.2 | `.meta` 檔遺失或重生 | 被版控忽略、被誤刪、複製資料夾沒帶 `.meta` | GUID 改變，所有參照該資產的 prefab／場景全部變 Missing |
| 6.1.3 | 兩個資產 `.meta` GUID 衝突 | 複製資料夾後 `.meta` 一起複製 | 參照指向錯誤資產或隨機其一 |
| 6.1.4 | 改 `.asmdef` 名稱或搬移腳本到別的 asmdef | 腳本型別全名變更 | 既有序列化參照失效；需 `[MovedFrom]` 或重新掛載 |
| 6.1.5 | 在 prefab 內拖場景物件 | 資產不能引用場景物件 | 開啟後為 None，值沒保存 |

### 6.2 Prefab Variant 與覆寫
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 6.2.1 | Variant 覆寫值掩蓋基底 prefab 的更新 | 子層已覆寫該欄位，之後改基底同欄位 | 改基底沒效果；難追某個 variant 為何不更新 |
| 6.2.2 | 場景內實例有未套用的 prefab 覆寫 | 直接改場景實例卻沒 Apply | 該場景行為與 prefab 不一致；他人改 prefab 後此處仍是舊值 |
| 6.2.3 | 基底 prefab 新增或移動子物件／元件 | 覆寫路徑對不上 | 覆寫失效或被丟棄 |
| 6.2.4 | 深層 Variant 鏈 | 繼承層次過深 | 修改影響範圍難以預測（見 §32） |

### 6.3 場景參照
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 6.3.1 | 跨場景拖參照 | Unity 不允許序列化跨場景物件參照 | 欄位顯示 None 或 Type mismatch；需另行解析 |
| 6.3.2 | `LoadSceneMode.Single` 切場景 | DontDestroyOnLoad 以外的物件全部銷毀 | 持有舊場景物件參照的單例、靜態欄位變偽 null |
| 6.3.3 | 場景檔多人同時修改 | YAML 合併衝突 | 合併後遺失物件或參照；建議拆場景、用 prefab、啟用 UnityYAMLMerge |
| 6.3.4 | `LoadScene(int)` 用 Build Settings 索引 | 新增場景後索引錯位 | 載到錯誤場景 |

---

## 7. 資源載入與記憶體

### 7.1 Resources 資料夾
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 7.1.1 | Resources 資料夾內所有資源都被打進 Build | 不論有無被引用 | 包體膨脹、啟動時索引載入變慢 |
| 7.1.2 | `Resources.Load` 路徑字串錯（大小寫、副檔名） | 路徑錯誤 | 回傳 null，到使用時才 NRE |

### 7.2 AssetBundle
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 7.2.1 | 同一個 AssetBundle 被重複載入 | `LoadFromFile` 同一 bundle 兩次 | 例外「another AssetBundle with the same files is already loaded」 |
| 7.2.2 | `Unload(false)` 與 `Unload(true)` 選錯 | `false` 保留已載入物件但失去來源，`true` 連同物件一起卸 | `false` 造成記憶體洩漏與日後重複載入；`true` 造成場上物件材質或貼圖丟失（粉紅色） |
| 7.2.3 | 依賴 bundle 沒先載入 | 資源依賴另一 bundle 的貼圖／Shader | 材質粉紅、Shader 丟失、參照為 null |
| 7.2.4 | 共用資源被重複打進多個 bundle | 沒有獨立共用 bundle，隱式依賴被複製 | 包體膨脹，記憶體中同一資源存在多份 |
| 7.2.5 | Bundle 版本與程式碼版本不匹配 | 腳本型別樹（TypeTree）改變 | 反序列化失敗或欄位錯位 |
| 7.2.6 | 關閉 TypeTree 減小體積 | 打包時不含型別資訊 | 客戶端程式更新後，舊 bundle 載入時資料損壞或崩潰 |
| 7.2.7 | Bundle 內 Shader 變體缺失 | 變體在 Build 時被剝離 | 材質顯示粉紅或錯誤渲染（見 §22） |
| 7.2.8 | `LoadFromMemory` 保留整份 byte[] | 檔案副本與解壓資料並存 | 記憶體翻倍；行動端 OOM |
| 7.2.9 | 主工程腳本與 bundle 內 prefab 的序列化格式不同步 | 主工程更新導致序列化格式變動 | 與舊 bundle 不匹配（熱更尤其重要，見 §14） |

### 7.3 Addressables
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 7.3.1 | 載入沒有對應 Release | 每次載入增加引用計數，要手動 Release 才減少 | 資源與所屬 bundle 永遠不卸載，記憶體持續上升〔官〕 |
| 7.3.2 | 只釋放結果、沒釋放 Handle | 引用計數掛在 Handle 上 | 計數沒減少，洩漏〔社〕 |
| 7.3.3 | `InstantiateAsync` 產生的物件用 `Destroy` 銷毀 | `Destroy` 不減少 Addressables 引用計數；需 `ReleaseInstance` | 實例消失但 bundle 永遠卸不掉〔社〕 |
| 7.3.4 | Release 不等於立即釋放記憶體 | 記憶體在整個 bundle 都沒引用時才釋放；`UnloadUnusedAssets` 很慢 | 以為 Release 就回收，記憶體曲線沒掉；同 bundle 其他資源仍佔著〔官〕 |
| 7.3.5 | 在 Awake 或同步程式碼用 `WaitForCompletion` | 主執行緒阻塞等載入 | 卡頓；WebGL 上死鎖或不支援 |
| 7.3.6 | Catalog 更新與內容版本不一致 | 遠端 catalog 更新但本機 bundle 舊 | 找不到 key，或載到舊內容 |
| 7.3.7 | Group 用「Pack Together」把不相干資源打在一起 | 一個資源用到，整包載入 | 記憶體被不需要的資源佔滿 |
| 7.3.8 | 隱式依賴重複 | 兩個 group 都依賴未標記 Addressable 的同一資源 | 該資源被複製到兩個 bundle，記憶體翻倍 |
| 7.3.9 | Address／Label 用字串 | 改名即失效 | 執行期才發現；應優先 `AssetReference` |
| 7.3.10 | 場景用 Addressables 載入後只切場景、沒 Release | 要用 `UnloadSceneAsync` 並 Release | 場景資源殘留 |

### 7.4 記憶體不釋放與重複載入
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 7.4.1 | 資源被靜態欄位、單例、事件持有 | 參照不斷 | 切場景後記憶體不降，累積成 OOM |
| 7.4.2 | `Resources.UnloadUnusedAssets` 當萬靈丹 | 它只卸載無參照資源，且很慢 | 有殘留參照則無效；時機不當造成卡頓〔官〕 |
| 7.4.3 | Texture 未開 `isReadable` 卻在執行期讀像素 | Read/Write 關閉 | 例外；反之不必要地開啟則記憶體翻倍（CPU 側一份、GPU 側一份） |
| 7.4.4 | 執行期建立的 `Texture2D`／`Sprite.Create` 沒 `Destroy` | native 資源 | 持續洩漏 |
| 7.4.5 | `RenderTexture` 沒 `Release()` | 每個佔 GPU 記憶體 | GPU 記憶體洩漏、行動端崩潰 |
| 7.4.6 | Mipmap 設定不當 | UI 貼圖開 mipmap，或 3D 貼圖沒開 | UI 多佔約 33% 記憶體；3D 遠處閃爍 |
| 7.4.7 | 貼圖壓縮格式與平台不符 | 例如平台不支援該壓縮格式，匯入時解壓成 RGBA32 | 記憶體暴增數倍，且無明顯警告 |
| 7.4.8 | 音訊 `Load Type` 選錯 | 長音樂選 Decompress On Load | 一首背景音樂佔數十 MB |
| 7.4.9 | 戰鬥中同步載入大型 Prefab | 瞬時 Instantiate 加反序列化 | 單幀卡數百 ms |

### 7.5 Sprite Atlas
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 7.5.1 | Sprite 沒有進圖集 | 未打包或被排除 | 每個 Sprite 一個 draw call，UI 合批失敗 |
| 7.5.2 | 圖集內容與使用情境不匹配 | 不同介面的圖塞同一圖集 | 只用一張圖卻載入整張圖集 |
| 7.5.3 | 同一張 Sprite 被打進多個圖集 | 重複打包 | 資源重複，記憶體翻倍 |
| 7.5.4 | 動態 UI 圖片（頭像、截圖）用 `Sprite.Create` | 不走圖集，不合批 | 每張一個 draw call 與一份獨立貼圖 |

---

## 8. UI（UGUI／TMP／UI Toolkit）

### 8.1 UGUI Rebuild 與 Canvas
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 8.1.1 | 單一 Canvas 放全部 UI | 任一元素變動，整個 Canvas 的批次重建 | 每幀 `Canvas.BuildBatch` 耗時高〔官〕 |
| 8.1.2 | 每幀移動／縮放 RectTransform（跑馬燈、血條跟隨） | 觸發所屬 Canvas 重建 | 動態元素應切到獨立子 Canvas〔官〕 |
| 8.1.3 | 過度切分 Canvas | 每個 Canvas 產生自己的批次 | draw call 增加，反而更慢〔官〕 |
| 8.1.4 | Layout Group（Horizontal／Vertical／Grid）巢狀 | 子元素變動引發連鎖 Layout 重算 | 打開介面或刷新列表時卡頓；多層巢狀成本指數上升 |
| 8.1.5 | `ContentSizeFitter` 與 Layout Group 互相依賴 | 計算順序迴圈 | 尺寸抖動，需多幀才穩定，或輸出警告 |
| 8.1.6 | 同幀設定 UI 後立刻讀 RectTransform 大小 | Layout 尚未計算 | 讀到舊值；需 `LayoutRebuilder.ForceRebuildLayoutImmediate`（昂貴）或等下一幀 |
| 8.1.7 | `SetActive(false)/true` 大量切換 UI | 每次啟用重建 Layout 與 Graphic | 切頁卡頓；可改用 `CanvasGroup.alpha` 或移出畫面（但 raycast 與動畫仍需處理） |
| 8.1.8 | 大型 ScrollView 不做虛擬化 | 數百上千個 item 全部實例化 | 記憶體高、開啟慢、Layout 成本爆炸 |
| 8.1.9 | UI 上放不必要的 Mask／RectMask2D 巢狀 | Mask 打斷合批，產生 stencil 切換 | draw call 暴增、填充率問題 |

### 8.2 Raycast 與 EventSystem
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 8.2.1 | 不需要互動的 Image／Text 保留 `Raycast Target` | 預設開啟 | 每次點擊都對這些元素做射線檢測；且透明元素阻擋下層點擊 |
| 8.2.2 | 透明但開 Raycast Target 的全螢幕元素 | 擋住下方按鈕 | 按鈕「點不到」，很難查 |
| 8.2.3 | 沒有 EventSystem | 新場景漏放 | UI 完全不響應 |
| 8.2.4 | 點擊穿透 UI 到 3D 場景 | 用 `Input.GetMouseButtonDown` 而沒檢查 `EventSystem.IsPointerOverGameObject` | 點按鈕同時觸發場景操作 |
| 8.2.5 | 觸控裝置上 `IsPointerOverGameObject()` 不帶 fingerId | 觸控與滑鼠語意不同 | 觸控時永遠回 false 或誤判 |
| 8.2.6 | Button `onClick` 沒防連點 | 無冷卻 | 重複送出請求、重複扣款、雙重轉場 |
| 8.2.7 | `onClick.AddListener` 重複註冊 | 每次開介面都 AddListener 沒清除 | 一次點擊觸發多次 |
| 8.2.8 | 以 `AddListener` 註冊 lambda，之後無法 `RemoveListener` | 匿名委派無參考 | 無法解除，造成洩漏與重複觸發（見 §12） |

### 8.3 Text／TextMeshPro
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 8.3.1 | 字型字元缺失 | 動態字型圖集沒有該字（中文、emoji） | 顯示方框或空白；TMP 需設定 Fallback Font |
| 8.3.2 | 在 Update 內設定 `text` 賦相同內容 | 觸發重新生成 mesh | 每幀重建文字網格，CPU 與 GC 熱點 |
| 8.3.3 | Rich Text 標籤來自玩家輸入 | 玩家輸入含 `<size=…>` 之類標籤 | 版面被破壞、UI 注入；需跳脫 |
| 8.3.4 | 文字溢出沒處理 | 多語系字串長度差異大 | 文字超出框外、被截斷；需 Auto Size 或預留空間 |

### 8.4 UI Toolkit（UXML／USS）
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 8.4.1 | 在 `Awake`／`OnEnable` 查詢 `rootVisualElement` | 文件尚未建構完成 | 查詢回 null |
| 8.4.2 | `Q<T>("name")` 查詢字串名稱 | 改名即失效 | 靜默 null；每次查詢有成本，需快取 |
| 8.4.3 | 事件回呼註冊後沒 `UnregisterCallback` | 元素被移除重建 | 洩漏與重複觸發 |
| 8.4.4 | 執行期 UI Toolkit 與 UGUI 並存 | 兩套輸入、排序、事件系統 | 點擊穿透、排序錯亂、焦點爭奪 |

---

## 9. 動畫與物理

### 9.1 Animator
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 9.1.1 | Animator 參數字串寫錯 | 無編譯期檢查 | 靜默無效，不報錯（既有 A-39、H10 同類） |
| 9.1.2 | `SetTrigger` 後沒被消耗 | Trigger 在沒有對應轉換時會殘留 | 稍後在不該觸發的時機突然觸發；需 `ResetTrigger` |
| 9.1.3 | 同幀 `SetTrigger` 多個 | 兩個 Trigger 競爭同一個轉換 | 狀態機走向隨機或跳過 |
| 9.1.4 | `Animator.Play` 與 `CrossFade` 當幀不生效 | 要到下一次 Animator 更新才套用 | 同幀讀取狀態得到舊值 |
| 9.1.5 | Animation Event 呼叫已不存在或改名的方法 | 字串綁定 | 運行時報錯 "has no receiver"；或靜默 |
| 9.1.6 | Animator 停用後再啟用，狀態重置 | 預設 `Keep Animator State On Disable` 關閉 | 動畫從頭播放、參數回到預設 |
| 9.1.7 | Root Motion 與腳本移動並存 | 兩者都在改 transform | 位移加倍或抖動 |

### 9.2 Rigidbody 與 Transform
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 9.2.1 | 直接改 `transform.position` 移動帶 Rigidbody 的物件 | 繞過物理引擎，等於瞬間傳送 | 穿牆、碰撞錯過、速度與位置不一致 |
| 9.2.2 | 在 Update 中改 `Rigidbody.velocity`／`AddForce` | 時機不在物理步進內 | 受力與幀率相關（AddForce 在 Update 呼叫多寡取決於幀數） |
| 9.2.3 | 修改 `transform` 後，物理世界未同步 | 預設 `Auto Sync Transforms` 在新版本為關閉 | 同幀內 Raycast／碰撞用的是舊位置；需 `Physics.SyncTransforms` |
| 9.2.4 | Kinematic Rigidbody 用 `transform` 移動而非 `MovePosition` | 無法計算推動其他物體的速度 | 推不動別人，或穿過去 |
| 9.2.5 | 子彈類高速物體 | 一個物理步進移動距離大於牆厚 | 穿牆（Tunneling）；需 Continuous 碰撞偵測或射線預測 |
| 9.2.6 | 物理數值極端（質量比過大、速度極大） | 數值不穩定 | 抖動、彈飛、NaN 傳播 |
| 9.2.7 | Rigidbody 位置出現 NaN | 除以零、無限速度 | 物件消失、整個物理子系統警告，傳染到相鄰物件 |

### 9.3 固定步進與物理回呼
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 9.3.1 | 低幀率下 FixedUpdate 補跑造成物理螺旋 | 見 2.1.3 | 越卡越多補跑，最終幀率崩潰〔官〕 |
| 9.3.2 | `OnTriggerEnter`／`OnCollisionEnter` 需雙方至少一個有 Rigidbody | 兩個靜態碰撞體不產生回呼 | 回呼不觸發，找不到原因 |
| 9.3.3 | Trigger 與 Collision 回呼混淆 | `isTrigger` 勾選與否決定走哪組回呼 | 寫了 OnCollision 卻是 Trigger 碰撞體，永不觸發 |
| 9.3.4 | 2D 與 3D 物理混用 API | `Rigidbody` vs `Rigidbody2D`、`Physics` vs `Physics2D` | 用錯類別回傳 null 或空結果，無報錯 |
| 9.3.5 | 物理查詢（Raycast）打到自己 | 預設會命中發射者的碰撞體 | 判定永遠命中自己；需 LayerMask 或起點偏移 |

### 9.4 Layer 與碰撞矩陣
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 9.4.1 | Layer 用數字索引 | `1 << 8` 這類魔法數字 | 改了 Layer 設定後全錯（既有 F11 同類） |
| 9.4.2 | LayerMask 位元運算寫反 | 傳入 layer index 而非 mask | Raycast 命中錯層或全不命中 |
| 9.4.3 | Layer Collision Matrix 專案設定被改 | 設定存於 ProjectSettings | 碰撞突然失效或新增，與程式無關卻改變行為 |

---

## 10. 時間與幀率

### 10.1 deltaTime 與 timeScale
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 10.1.1 | 移動／計時未乘 `Time.deltaTime` | 以「每幀」為單位 | 速度隨幀率變動；60Hz 與 120Hz 手機行為不同 |
| 10.1.2 | 在 FixedUpdate 乘 `Time.deltaTime` | 在 FixedUpdate 內 `deltaTime` 等於 `fixedDeltaTime` | 結果正確，但寫法混淆，搬到 Update 時出錯〔官〕 |
| 10.1.3 | `timeScale = 0` 暫停，但依賴 `Time.deltaTime` 的 UI 動畫停了 | deltaTime 為 0 | 暫停選單動畫不動；應用 `unscaledDeltaTime` |
| 10.1.4 | 全程用 `unscaledDeltaTime` | 慢動作、暫停時仍前進 | 戰鬥邏輯不受暫停影響，與設計不符 |
| 10.1.5 | 切後台、場景載入後恢復 `timeScale` 遺漏 | 暫停時切場景 | 新場景以 `timeScale = 0` 開始，畫面不動 |
| 10.1.6 | 高 `timeScale` 加速 | 物理與 FixedUpdate 次數增加 | 步進過多，補跑量增加；超過 `maximumDeltaTime` 時模擬被截斷〔官〕 |
| 10.1.7 | 第一幀 `deltaTime` 異常大 | 載入場景造成長幀 | 角色一幀飛出去；需夾限 deltaTime |
| 10.1.8 | 從後台恢復的第一幀 deltaTime | 切回前台後巨大跳變 | 計時器、冷卻一次走完；需用 `maximumDeltaTime` 與自行處理 |

### 10.2 幀率與 VSync
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 10.2.1 | 遊戲邏輯綁定幀率 | 假設固定 30/60 FPS | 高刷新率裝置（90/120/144Hz）上邏輯變快 |
| 10.2.2 | `Application.targetFrameRate` 與 `vSyncCount` 並用 | 兩者互相作用，vSync 開啟時 targetFrameRate 被忽略（依平台） | 以為鎖了 30 幀實際 60 幀；耗電與發熱超預期〔官〕 |
| 10.2.3 | 以幀數計時（`frameCount % 60`） | 幀率不固定 | 「每秒一次」變成每 0.5 秒或 2 秒 |

### 10.3 真實時間與日期
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 10.3.1 | 用 `DateTime.Now` 做遊戲內冷卻或到期 | 玩家可修改裝置時間 | 作弊（改時間跳過冷卻）、時區變動造成錯誤 |
| 10.3.2 | 本機時間與伺服器時間混用 | 兩個時鐘源 | 到期判斷不一致（既有 C7 同類） |
| 10.3.3 | 夏令時與時區 | `Local` 與 `Utc` 混用 | 每日重置時間錯一小時，或重複觸發 |
| 10.3.4 | 裝置時間倒退 | 玩家調整系統時間 | 負的時間差；計時器溢位或逆行 |
| 10.3.5 | 離線收益用本機時間差 | 時間可被改 | 無限收益 |

---

## 11. 浮點、決定性與隨機

### 11.1 浮點
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 11.1.1 | `float` 用 `==` 比較 | 浮點誤差 | 條件永遠為 false；Unity 的 `Mathf.Approximately` 對極小或極大值也不理想 |
| 11.1.2 | `float` 累加長時間 | 精度流失 | 計時、進度條、位置累積誤差 |
| 11.1.3 | NaN 與 Infinity 傳播 | 除以零、`Mathf.Sqrt(負數)`、`Normalize` 零向量 | 一個 NaN 污染整串計算；位置變 NaN 後物件消失 |
| 11.1.4 | `Vector3.normalized` 零向量 | 回傳零向量而非例外 | 後續方向計算靜默錯誤 |
| 11.1.5 | 貨幣、機率用 `float` | 精度與捨入誤差 | 金額分毫對不上；應用整數或 `decimal`（客戶端顯示層尤其注意） |
| 11.1.6 | `Mathf.Lerp` 用 `Time.deltaTime` 當 t | 常見的「平滑」寫法 | 結果與幀率相關，不是真正的指數衰減 |

### 11.2 決定性（鎖步、回放、客戶端預測）
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 11.2.1 | 不同 CPU／平台浮點結果不同 | 指令集（FMA）、編譯器優化、IL2CPP 與 Mono 差異 | 鎖步同步（Lockstep）在不同裝置上漸漸分歧（desync） |
| 11.2.2 | Burst 與非 Burst 結果不同 | 見 3.3.7 | 同一邏輯兩條路徑結果微差 |
| 11.2.3 | `Dictionary`／`HashSet` 迭代順序 | 不保證順序 | 回放、同步時順序不同導致結果不同 |
| 11.2.4 | `UnityEngine.Random` 全域狀態 | 任一模組呼叫都會推進狀態 | 加入新功能後所有隨機結果改變，回放失效 |
| 11.2.5 | 物理引擎不保證跨機決定性 | PhysX 內部步進、平台差異 | 物理驅動的玩法無法做鎖步 |
| 11.2.6 | 用 `Time.deltaTime` 驅動模擬 | 每台機器幀時間不同 | 模擬結果依賴機器；鎖步須用固定步進與整數／定點數 |
| 11.2.7 | 客戶端預測與伺服器結果浮點不同 | 兩端語言或平台不同 | 持續修正拉扯、畫面抖動（既有 C3） |

### 11.3 隨機
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 11.3.1 | `Random.Range(int, int)` 上界為開區間、`float` 版為閉區間 | 兩版本語意不同 | int 版永遠取不到上界；float 版邊界可取 |
| 11.3.2 | 每次 `new System.Random()` 以時間為種子 | 短時間內多次建立得到相同種子 | 同一刻產生的隨機序列相同 |
| 11.3.3 | `Random.InitState` 設定全域種子後忘記還原 | 影響其他系統 | 關卡生成固定種子後，其餘隨機也被固定 |
| 11.3.4 | 用客戶端隨機決定掉落、抽獎結果 | 結果可被修改 | 作弊；權威結果應在伺服器（既有 A1、A3） |
| 11.3.5 | 「保底」機率用客戶端累計計數 | 客戶端存檔可改 | 保底計數被竄改 |

---

## 12. 事件、委派與單例殘留

### 12.1 事件與委派洩漏
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 12.1.1 | `static event` 訂閱未退訂 | 靜態事件源永遠活著，持有訂閱者參照 | 被銷毀的 MonoBehaviour 殼無法回收，回呼仍被呼叫 → MissingReferenceException（既有 B05、A-15） |
| 12.1.2 | 在 `OnEnable` 訂閱但沒在 `OnDisable` 退訂 | 生命週期不配對 | 重複訂閱、事件觸發多次 |
| 12.1.3 | 在 `Awake`/`Start` 訂閱，在 `OnDisable` 退訂 | 重新啟用時不再訂閱 | 物件停用再啟用後收不到事件 |
| 12.1.4 | 匿名 lambda 訂閱 | 無法對應 `-=` | 無法退訂 |
| 12.1.5 | 事件回呼拋例外 | 多播委派中途中斷 | 後面的訂閱者都沒被呼叫；狀態不一致 |
| 12.1.6 | 事件在物件銷毀後觸發回呼 | 訂閱者已被銷毀但仍在清單 | 回呼對偽 null 物件操作 |

### 12.2 DontDestroyOnLoad 與單例
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 12.2.1 | 單例在場景重載時重複生成 | 每個場景都放一個，`DontDestroyOnLoad` 後再進入相同場景 | 出現兩個單例；需在 Awake 檢查並銷毀自己 |
| 12.2.2 | 單例的 `Instance` 在 Awake 前被存取 | 初始化順序 | 回 null，或在 getter 內自動建立導致重複 |
| 12.2.3 | 單例 getter 自動建立（`FindObjectOfType` 找不到就 new） | 退出階段也會觸發 | 關閉時復活物件、殘留（見 1.2.9） |
| 12.2.4 | `DontDestroyOnLoad` 物件持有場景物件參照 | 場景切換後被參照者被銷毀 | 單例內欄位變偽 null |
| 12.2.5 | 單例持有資源（貼圖、AssetBundle）永不釋放 | 單例壽命等於 App | 記憶體只增不減（見 7.4.1） |
| 12.2.6 | 靜態欄位在 Domain Reload 關閉的 Editor 中殘留 | 靜態狀態跨播放保留 | 第二次播放帶舊狀態；Build 無此問題，造成「Editor 才有」的 bug（見 §16） |

### 12.3 場景切換殘留
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 12.3.1 | 協程／Task／Timer 在場景切換後仍在跑 | 持有者在 DontDestroyOnLoad 物件 | 回呼對舊場景物件操作 |
| 12.3.2 | 舊場景的事件訂閱未清 | 場景卸載不會自動退訂 static 事件 | 事件觸發到已銷毀物件 |
| 12.3.3 | 舊場景的資源（Addressables handle）沒釋放 | 場景切換不等於資源釋放 | 記憶體堆疊 |
| 12.3.4 | 靜態快取存場景物件 | 例如 `static Dictionary<string, GameObject>` | 場景重載後全是偽 null |

---

## 13. IL2CPP／AOT／Code Stripping

### 13.1 AOT 泛型
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 13.1.1 | 執行期才決定的泛型實例（`MakeGenericType`、`MakeGenericMethod`） | AOT 編譯時推斷不到該實例 | 在 IL2CPP 平台 `ExecutionEngineException`；Editor 與 Mono 正常，上機才爆〔官〕 |
| 13.1.2 | 泛型虛擬方法的呼叫無法在編譯期推斷 | 屬於 IL2CPP 已知限制 | 找不到對應泛型實例 → 執行期例外〔官〕 |
| 13.1.3 | 值型別泛型實例未預先產生 | 值型別無法共用程式碼 | 缺實例時例外，或退化為較慢的共享路徑；可在永不被呼叫的輔助方法內引用以強迫產生〔官〕 |
| 13.1.4 | `Activator.CreateInstance` + 泛型 | 反射建立 AOT 沒生成的類型 | 例外或 null〔官〕 |
| 13.1.5 | JSON 函式庫（Newtonsoft）反序列化泛型集合、struct | 內部大量反射泛型 | 某些型別在 IL2CPP 失敗；需 AOT 輔助或 link.xml |
| 13.1.6 | 使用 `System.Reflection.Emit`、`dynamic`、`Expression.Compile` | AOT 平台不能在執行期產生程式碼 | 例外或退回直譯，效能暴跌 |

### 13.2 Code Stripping
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 13.2.1 | 只透過反射或字串使用的類別／方法被剝除 | Managed Code Stripping 靜態分析看不到引用 | Editor 正常，Build 後找不到型別／方法〔官〕 |
| 13.2.2 | 只被 AssetBundle 內 prefab 引用的 MonoBehaviour／類別被剝除 | 打主程式時沒有任何場景或程式碼引用該型別，stripping 認為未使用 | bundle 載入後元件 Missing（型別已被剝除）；需 link.xml 保留或在主工程留引用 |
| 13.2.3 | `link.xml` 沒寫或寫錯 | 保留規則缺漏 | 局部功能在 Release 失效，Development Build 正常 |
| 13.2.4 | `[Preserve]` 屬性遺漏 | 反射呼叫的成員 | 同上 |
| 13.2.5 | 第三方 SDK 需要保留規則但沒提供 | SDK 內部反射或 JNI | 在高強度 stripping 下初始化失敗 |
| 13.2.6 | Stripping Level 切換（Low/Medium/High）引起行為變化 | 不同等級保留範圍不同 | 提升等級省包體，卻破壞功能 |
| 13.2.7 | 事件系統用字串反射找方法（`SendMessage`、`Invoke`、`GetMethod`） | 方法被視為未使用 | 方法被剝除，呼叫靜默失敗 |
| 13.2.8 | 引擎或 IL2CPP 版本升級後剝除行為改變 | 靜態分析規則隨版本調整 | 升級後才出現的功能失效，與程式碼改動無關 |
| 13.2.9 | 只有 Release Build 失敗 | 開發版預設較少剝除 | 測試環境沒覆蓋 Release 設定 |

### 13.3 IL2CPP 其他限制
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 13.3.1 | 反射存取私有成員的效能與可用性 | IL2CPP 的元資料可用但慢 | 熱路徑反射大幅變慢（既有 E07、A-40） |
| 13.3.2 | `Marshal`、P/Invoke 簽名錯誤 | AOT 需要編譯期確定簽名 | 崩潰；委派 marshaling 需 `[MonoPInvokeCallback]` |
| 13.3.3 | 原生回呼委派傳給 native | 沒有 `[MonoPInvokeCallback]` | IL2CPP 上回呼崩潰（Mono 上正常） |
| 13.3.4 | 堆疊深度限制不同 | 各平台執行緒堆疊大小不同 | 在 Editor 沒事的深遞迴，在 Android/iOS 堆疊溢位直接崩潰 |

---

## 14. 熱更系統（ILRuntime／HybridCLR）

> 名詞：**主工程（AOT）**＝隨安裝包編譯成原生碼的 C#；**熱更工程**＝之後下載、由直譯器或補充元資料載入的 C# 組件。兩者之間的呼叫叫「跨域」。ILRuntime 是純直譯器（熱更類型在主工程眼中是黑盒）；HybridCLR 擴充 IL2CPP 使其能載入新組件並直譯執行（熱更類型是真正的 CLR 型別）。下列條目個別標示適用方案。

### 14.1 跨域呼叫與邊界
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 14.1.1 | 主工程靜態引用熱更型別 | AOT 組件不能依賴熱更組件，依賴方向只能是熱更→主工程〔社〕 | 編譯期或載入期失敗；變通成介面、委派、反射 |
| 14.1.2 | 熱更組件之間依賴順序 | 被依賴的組件需先載入〔社〕 | 載入順序錯 → 型別找不到 |
| 14.1.3 | 主→熱→主→熱的來回呼叫 | 一次邏輯多次穿越邊界（主工程事件 → 熱更處理 → 主工程工具 → 熱更回呼） | 每次穿越都有轉接成本與例外邊界；堆疊難追；偵錯斷點只在一邊有效 |
| 14.1.4 | 邊界上的例外 | ILRuntime 例外堆疊跨域混雜；熱更內拋出、主工程捕捉 | 堆疊資訊缺失或失真，Crash 報告無法對應行號 |
| 14.1.5 | 跨域傳遞 struct | ILRuntime 熱更 struct 在主工程眼中是黑盒；傳入主工程 API 需裝箱轉換 | 效能差、欄位遺失或型別不符例外（ILRuntime） |
| 14.1.6 | 熱更類別作為主工程泛型參數（`List<HotClass>`、`Dictionary<K, HotClass>`） | 主工程泛型實例無法用熱更型別 | ILRuntime 需註冊泛型實例；沒註冊 → 執行期例外或元素型別異常 |
| 14.1.7 | 熱更內使用主工程泛型的值型別實例（`List<MyStruct>`） | AOT 沒生成該實例 | HybridCLR：需補充元資料或預先實例化；否則例外或走慢速解釋路徑〔社〕 |
| 14.1.8 | 熱更版本與主工程版本不匹配 | 主工程改了簽名／欄位／泛型，熱更 DLL 仍依舊版 | 載入後 `MissingMethodException`／`TypeLoadException`／欄位錯位 |
| 14.1.9 | 熱更程式碼呼叫已被 stripping 剝除的主工程 API | AOT 組件裁剪後缺方法 | 執行期例外；需在主工程保留（link.xml）並以裁剪後的 DLL 產生熱更橋接〔社〕 |

### 14.2 繼承、委派與適配（ILRuntime 重點）
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 14.2.1 | 熱更類別繼承主工程類別／介面 | ILRuntime 需手寫 CrossBindingAdaptor（跨域繼承適配器） | 沒寫 → 執行期例外；寫錯 → 虛方法、base 呼叫、屬性行為不對 |
| 14.2.2 | 主工程類別繼承熱更類別 | 方向反了，不可能在 AOT 靜態表達 | 設計錯誤，需改為介面或回呼 |
| 14.2.3 | 熱更代碼中的委派傳給主工程 | 需註冊 DelegateConvertor（把熱更委派轉成主工程委派型別） | 沒註冊 → 例外；註冊但簽名不同 → 呼叫錯參數 |
| 14.2.4 | 熱更 lambda／匿名委派傳給主工程 API | 每次轉換產生轉接物件 | 配置增加；拿不到原委派，無法 `-=` 退訂（見 12.1.4） |
| 14.2.5 | `IEnumerator` 跨域（熱更 coroutine 交給主工程 `StartCoroutine`） | 需要 IEnumerator 適配器 | 沒註冊 → 例外或 coroutine 不執行（ILRuntime） |
| 14.2.6 | 熱更類別當 `UnityEvent` 目標、Animation Event 目標 | Unity 以主工程型別資訊序列化 | 序列化資料找不到熱更型別，事件失效 |
| 14.2.7 | 適配器與委派轉換沒有集中註冊清單 | 散落各處，漏註冊 | 只在特定功能觸發才爆，QA 覆蓋不到 |
| 14.2.8 | 適配器在產生程式碼後被手改 | 下次重新產生被覆蓋 | 修正消失，bug 回歸 |
| 14.2.9 | 虛方法重寫的 `base.Method()` 呼叫 | 跨域繼承下 base 呼叫經由適配器遞迴 | 無窮遞迴 → 堆疊溢位（適配器寫法錯的典型症狀） |

### 14.3 MonoBehaviour 與資源綁定
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 14.3.1 | 熱更 MonoBehaviour 直接掛 prefab | HybridCLR 支援；ILRuntime 不支援，需用主工程的包裝 MonoBehaviour 轉發 | ILRuntime 專案若直接用 → 腳本 Missing；轉發層則多一跳 |
| 14.3.2 | prefab 在熱更組件載入前被載入／實例化 | 腳本型別尚不存在 | 元件 Missing，且 prefab 序列化資料已損壞（需重載） |
| 14.3.3 | 熱更腳本 GUID／fileID 與打包時不一致 | 組件重新編譯、改名、搬移 | bundle 內 prefab 的腳本參照失效 |
| 14.3.4 | 熱更 MonoBehaviour 使用 `[RuntimeInitializeOnLoadMethod]` | 屬於引擎啟動階段，早於熱更組件載入 | 不會被呼叫（經驗，需對照所用方案文件） |
| 14.3.5 | ScriptableObject／序列化資料引用熱更型別 | 同 14.3.2 | 載入時型別缺失 |
| 14.3.6 | 熱更組件載入時機晚於第一個場景的資源 | 啟動流程設計 | 第一個場景含熱更腳本 → Missing；需「啟動場景只含主工程」 |
| 14.3.7 | 熱更 DLL 內嵌 `[SerializeField]` 欄位改名 | 序列化資料以名稱對應 | 資料遺失（同 5.1.3），而且熱更後無法 `FormerlySerializedAs` 回溯舊資源 |

### 14.4 字串反射、型別查找與元資料
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 14.4.1 | `Type.GetType("Namespace.Class")` 找熱更型別 | 只搜尋呼叫者組件與 mscorlib；熱更型別在另一個組件 | 回 null；需限定組件名或自行維護型別表 |
| 14.4.2 | 以字串名稱建立／註冊類別（工廠、命令表、協定表） | 熱更後新型別名稱與表不一致 | 靜默找不到；重構改名即壞（既有 A-39） |
| 14.4.3 | `Assembly.GetTypes()` 掃描所有型別 | 載入的熱更組件數量與順序不同 | 掃描結果隨載入狀態不同；效能差 |
| 14.4.4 | 熱更組件載入後主工程反射快取過期 | 先快取了型別表，之後才載入熱更 | 新型別不在快取內 |
| 14.4.5 | 兩個組件有同名型別 | 熱更新增與主工程重名 | `AmbiguousMatch`，或載到非預期版本 |
| 14.4.6 | 熱更組件重複載入 | 熱更流程重入 | HybridCLR 對同一組件重複載入補充元資料有明確錯誤〔社〕；或組件內靜態狀態重置 |
| 14.4.7 | 熱更組件無法卸載 | .NET Core 式 AssemblyLoadContext 不可用 | 舊版熱更程式碼常駐記憶體，多版本疊加 |

### 14.5 值型別、泛型與效能（HybridCLR）
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 14.5.1 | 補充元資料的泛型函式以直譯方式執行 | AOT 沒有該泛型實例 | 比原生慢很多；熱路徑（每幀）用到會掉幀，建議用工具收集泛型並預先在 AOT 實例化〔社〕 |
| 14.5.2 | 補充元資料模式選錯（Consistent／SuperSet） | Consistent 只能搭配裁剪後的 AOT DLL | 用錯來源 DLL → 載入失敗或資料不符〔社〕 |
| 14.5.3 | 補充元資料的 AOT DLL 與打包版本不精確匹配 | 元資料來自不同次打包 | 載入失敗或後續執行期例外〔社〕 |
| 14.5.4 | 非 AOT 組件被當作補充元資料載入 | 流程錯誤 | 載入報錯〔社〕 |
| 14.5.5 | 熱更程式的整體直譯效能 | 直譯器比 AOT 慢一個量級 | 戰鬥計算、尋路、大量迴圈放熱更端 → 掉幀；需把重運算放主工程 |
| 14.5.6 | 熱更中 `unsafe`、`stackalloc`、`fixed`、SIMD 特殊型別 | 直譯器對底層特性支援有限（以所用版本文件為準） | 行為不同或不支援 |
| 14.5.7 | 熱更回呼給 native 的函式指標（`[MonoPInvokeCallback]`、`Marshal.GetFunctionPointerForDelegate`） | 需要預先生成橋接函式 | 沒生成 → 回呼時崩潰 |
| 14.5.8 | 熱更版更新後，舊熱更狀態（靜態欄位、單例）仍存活 | 沒有重啟 | 新舊程式碼並存，行為不一致；強烈建議熱更後重啟或重新初始化 |

### 14.6 熱更流程與版本
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 14.6.1 | 熱更下載未驗證 hash／簽章 | 傳輸損毀或被竄改 | 載入損毀 DLL 崩潰，或執行被置換的程式碼（安全風險） |
| 14.6.2 | 熱更失敗沒有回退機制 | 新版 DLL 有 bug | 玩家卡在無法啟動，只能重裝 |
| 14.6.3 | 熱更與主程式「最低相容版本」沒有強制檢查 | 舊安裝包收到不相容的熱更 | 方法簽名、欄位不符 → 啟動即崩 |
| 14.6.4 | 熱更內容與資源（bundle）版本不配對 | 分別更新 | 腳本與資料格式不一致 |
| 14.6.5 | 熱更程式碼被快取在本機且更新失敗時載入舊版 | 部分檔案更新 | 組件之間版本混搭 |
| 14.6.6 | 審核平台政策 | 部分平台限制下載可執行程式碼 | 上架被拒或下架（需對照各平台現行規範，本表不下結論） |
| 14.6.7 | 開發階段 Editor 直接引用熱更程式，Build 才走載入流程 | 兩條路徑 | Editor 一切正常，真機載入流程才暴露問題；應在 Editor 也走相同載入路徑 |
| 14.6.8 | 熱更組件的符號（PDB）不隨發布 | 例外堆疊無行號 | 線上問題難定位 |

---

## 15. 平台與行動端

### 15.1 記憶體與生命週期
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 15.1.1 | 行動端記憶體上限遠低於開發機 | 系統依裝置給 App 的配額 | 低階機被系統殺掉（OOM Kill），沒有 Unity 例外，只有 App 消失 |
| 15.1.2 | 背景切換時被系統殺掉 | App 在背景佔用記憶體高 | 回前台時冷啟動，玩家認為閃退 |
| 15.1.3 | `OnApplicationPause(true)` 內做重工作 | 系統給的背景時間極短 | 工作未完成就被凍結／殺掉；存檔寫一半 |
| 15.1.4 | 回前台後沒重新同步狀態 | 計時器、連線、時間差 | 連線已斷、伺服器時間已前進；Update 的 deltaTime 巨大（見 10.1.8） |
| 15.1.5 | `OnApplicationFocus` 與 `OnApplicationPause` 順序與觸發時機平台不同 | iOS 與 Android 差異；系統對話框也會觸發 Focus 變化 | 邏輯重複或遺漏；權限彈窗、廣告、分享視窗皆會觸發 |
| 15.1.6 | 系統記憶體警告沒處理 | `Application.lowMemory` 沒訂閱 | 不釋放快取，繼續配置 → 被殺 |
| 15.1.7 | 螢幕休眠 / 鎖屏 | `Screen.sleepTimeout` 預設 | 玩家掛機被鎖屏，連線斷；或強制不休眠導致耗電 |

### 15.2 權限與系統功能
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 15.2.1 | 權限請求被拒絕或「不再詢問」 | Android 需 runtime 權限 | 功能靜默失效（相機、麥克風、儲存、通知）；需引導至設定頁 |
| 15.2.2 | 權限請求是非同步 | 立即讀取結果 | 讀到尚未授權的狀態 |
| 15.2.3 | 權限彈窗期間 App 失焦 | 觸發 Pause／Focus | 流程被打斷，重入 |
| 15.2.4 | 儲存路徑差異（`persistentDataPath` vs 外部儲存） | Android 分區儲存 | 檔案不可見、其他 App 不能讀、重裝後消失 |
| 15.2.5 | iOS 隱私清單與使用描述 | 缺描述字串 | 審核被拒或直接崩潰 |
| 15.2.6 | 推播／深度連結 / 啟動參數 | 冷啟動與熱啟動路徑不同 | 只處理一種路徑，另一種漏掉 |

### 15.3 螢幕與解析度
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 15.3.1 | 瀏海／圓角／手勢條 | 沒處理 `Screen.safeArea` | UI 被遮擋 |
| 15.3.2 | 解析度縮放策略 | CanvasScaler 參考解析度與長寬比 | 不同比例裝置 UI 跑位 |
| 15.3.3 | 螢幕旋轉／摺疊螢幕展開 | 解析度與方向動態變化 | 重新排版事件漏處理 |
| 15.3.4 | `Screen.width/height` 在 Awake 時機不準 | 平台啟動時尚未穩定 | 第一次排版用錯尺寸 |

### 15.4 平台差異與條件編譯
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 15.4.1 | `#if UNITY_ANDROID` 分支只在該平台編譯 | 其他平台不編譯該程式碼 | 語法錯誤、遺漏在其他平台才暴露 |
| 15.4.2 | `Application.platform` 與條件編譯混用 | 執行期與編譯期判斷不同 | Editor 模擬平台時行為不同 |
| 15.4.3 | 執行緒與特定 API 在 WebGL 不可用 | 瀏覽器限制 | `Thread`、同步 IO、Socket 無法使用 |
| 15.4.4 | GPU 與圖形 API 差異（Metal/Vulkan/GLES） | 驅動 bug、Shader 差異 | 特定機型畫面異常，開發機無法重現 |

---

## 16. Editor 與 Runtime 混用

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 16.1 | 執行期程式碼直接用 `UnityEditor` 命名空間 | Build 時 Editor 組件不存在 | Build 編譯失敗；用 `#if UNITY_EDITOR` 包住則行為在 Build 中消失 |
| 16.2 | `#if UNITY_EDITOR` 內放遊戲邏輯 | Editor 與 Build 邏輯分岔 | Editor 測試通過，Build 才出錯（既有 A-47） |
| 16.3 | Editor-only 欄位被序列化 | `#if` 包住欄位 | 在 Editor 與 Build 的序列化佈局不同，資料錯位 |
| 16.4 | 使用 `AssetDatabase.LoadAssetAtPath` 於執行期 | 僅 Editor 可用 | Build 中無法使用；在 Editor 中載入的資源不會被打包進 Build |
| 16.5 | 在 Editor 以路徑載入資源，Build 時該資源未被引用而被剔除 | 只存在於 Editor 能找到 | Build 後資源缺失 |
| 16.6 | Domain Reload 關閉（Enter Play Mode Options） | 為了加速進入播放 | 靜態欄位、靜態事件、單例殘留上次播放狀態；Build 無此問題（見 12.2.6） |
| 16.7 | Editor 腳本放在非 `Editor` 資料夾且無 asmdef 隔離 | 被編進 Runtime 組件 | Build 失敗或把 Editor 程式碼打進包 |
| 16.8 | `OnValidate`／`Reset` 中改資料 | 只在 Editor 呼叫 | 欄位在 Build 中沒有被補（見 1.1.9） |
| 16.9 | `[ExecuteAlways]` 腳本在 Editor 內修改資料 | 編輯模式下也跑 | 場景被意外改動並存檔 |
| 16.10 | 以 Editor 的 Development 設定驗證 Release 行為 | 預設較少剝除、有安全檢查 | Release 才暴露 stripping、越界等問題（見 3.3.8、13.2.9） |
| 16.11 | Editor 的「熱重載」重新編譯保留狀態 | 序列化欄位保留、非序列化欄位重置 | 播放中改程式碼後狀態不一致，產生只有熱重載才有的 bug |

---

## 17. 存檔與本地資料

### 17.1 PlayerPrefs
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 17.1.1 | 用 PlayerPrefs 存大量或結構化資料 | 它是為偏好設定設計 | 容量受限、讀寫效能差、平台實作不同（Windows 存登錄檔，有大小限制） |
| 17.1.2 | PlayerPrefs 存玩家重要進度 | 明文、可被修改、可被清除 | 作弊與資料遺失；移除 App 後消失 |
| 17.1.3 | `PlayerPrefs.Save()` 沒呼叫就當機 | 預設只在適當時機（退出）寫入 | 近期變更遺失 |
| 17.1.4 | `Save()` 過度呼叫 | 每次改值就存 | 磁碟 IO 卡頓 |
| 17.1.5 | Key 為字串散落各處 | 拼錯或重複 | 讀到預設值而非已存值；覆蓋別人的 key |
| 17.1.6 | `GetInt` 預設值與「從未存過」混淆 | 預設 0 | 無法分辨「玩家選 0」與「沒設過」；需 `HasKey` |
| 17.1.7 | `PlayerPrefs.DeleteAll` 誤用 | 清除偏好時連同進度一起清 | 玩家全部資料消失 |

### 17.2 檔案存檔與 JSON
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 17.2.1 | 直接覆寫存檔檔案 | 寫到一半當機或被殺 | 檔案損壞，玩家全部進度遺失；應先寫暫存檔再原子替換，並保留備份 |
| 17.2.2 | 存檔沒有校驗碼或版本號 | 讀到損壞或舊格式檔 | 反序列化失敗 → 例外或讀成預設值，靜默清空進度 |
| 17.2.3 | 讀檔失敗時回預設並自動覆寫 | 例外被吞，用空資料開始並存檔 | 損壞檔被空檔覆蓋，無法救援 |
| 17.2.4 | 存檔格式版本遷移缺失 | 新增／改名欄位 | 舊玩家升級後欄位為預設，或載入失敗 |
| 17.2.5 | 遷移程式只支援上一個版本 | 玩家跳版更新 | 跨多版的玩家資料無法升級 |
| 17.2.6 | `JsonUtility` 無法處理 Dictionary、多型 | 見 5.2.7 | 存讀後資料缺失 |
| 17.2.7 | Newtonsoft 在 IL2CPP 的泛型問題 | 見 13.1.5 | 真機載入存檔失敗 |
| 17.2.8 | 存檔路徑使用 `Application.dataPath` | 該路徑在行動端唯讀 | 寫檔失敗；應用 `persistentDataPath` |
| 17.2.9 | 在主執行緒同步存大檔 | 單幀長卡頓 | 存檔瞬間凍結；需背景序列化 + 主執行緒寫入或分批 |
| 17.2.10 | 明文存檔 | 玩家可直接修改 | 作弊；加密也只是提高門檻，權威資料應在伺服器 |
| 17.2.11 | 雲端存檔與本地存檔衝突 | 兩邊都有更新 | 以時間戳決勝則本機時鐘可被改；需明確合併規則與玩家選擇 |

### 17.3 本地資料表／設定檔
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 17.3.1 | 遊戲設定表（CSV/JSON/Excel 匯出）載入時整張進記憶體 | 大表 | 啟動慢、記憶體高 |
| 17.3.2 | 設定表的 ID 以字串或魔術數字參照 | 表改動後參照失效 | 執行期才發現找不到（既有 F11） |
| 17.3.3 | 設定表欄位型別驗證缺失 | 空白、格式錯 | 解析成 0 或預設值，靜默錯誤 |

---

## 18. 輸入

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 18.1 | 舊 Input Manager 與新 Input System 並存或切換 | Player Settings 的 Active Input Handling 設定 | 呼叫 `Input.GetKey` 在僅啟用新系統時拋 `InvalidOperationException` |
| 18.2 | 輸入字串（"Fire1"、"Horizontal"）寫死 | 拼錯或軸被改名 | 例外「Input Axis … is not setup」或靜默無效 |
| 18.3 | `GetKeyDown` 在 FixedUpdate 讀 | 見 2.1.1 | 漏輸入 |
| 18.4 | UI 上操作時穿透到場景 | 見 8.2.4 | 誤操作 |
| 18.5 | 新 Input System 的 Action 未啟用（`Enable()`）或未 `Dispose` | 啟用與釋放不對稱 | 輸入沒反應；或場景切換後重複觸發 |
| 18.6 | InputAction 回呼註冊後沒移除 | 同 12.1 | 洩漏與重複觸發 |
| 18.7 | Rebinding 資料存取與預設衝突 | 玩家改鍵後存檔 | 重置後仍沿用舊綁定，或不同裝置布局衝突 |
| 18.8 | 螢幕座標轉換（`ScreenToWorldPoint` 缺 z） | 沒給深度 | 回傳相機位置，物件跑到相機位置 |
| 18.9 | 暫停時仍接收遊戲輸入 | `timeScale = 0` 但邏輯用 unscaled | 暫停期間角色仍可操作 |

---

## 19. 多場景與場景載入

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 19.1 | `LoadSceneAdditive` 後場景內物件重複（兩個 EventSystem、兩個 AudioListener、兩個 Camera） | 每個場景都帶一份 | 警告「There are 2 audio listeners」、輸入重複 |
| 19.2 | `FindObjectOfType` 跨所有已載入場景搜尋 | 不限當前場景 | 找到別的場景的同型物件 |
| 19.3 | 非同步載入場景期間存取目標場景物件 | 尚未完成 | 取不到或取到半成品；需等 `sceneLoaded` / `completed` |
| 19.4 | `allowSceneActivation=false` 時的卡進度 | 見 2.4.1 | 載入畫面卡住 |
| 19.5 | 場景載入峰值記憶體 | 新場景載入時舊場景尚未釋放 | 瞬時記憶體翻倍 → 低階機 OOM；需中間空場景過渡 |
| 19.6 | 場景啟動順序依賴 Build Settings 的第一個場景 | 從 Editor 任意場景按播放 | Editor 從非啟動場景啟動時缺少初始化（單例、設定）；需 Bootstrap 機制 |

---

## 20. 物件池與 Instantiate／Destroy

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 20.1 | 物件取出後狀態未重設 | 池化物件保留上次的血量、速度、動畫、粒子 | 第二次使用出現怪異殘留（見 1.1.7） |
| 20.2 | 物件重複歸還 | 兩處都呼叫 Release | 同一物件在池中兩份，同時被兩個使用者取出，互相干擾 |
| 20.3 | 歸還後仍被持有並使用 | 持有者不知已歸還 | 「幽靈操作」另一個使用者的物件；需 handle 機制 |
| 20.4 | 池內物件被外部 `Destroy` | 其他模組銷毀了池中的物件 | 池取出偽 null |
| 20.5 | 場景切換時池與物件被銷毀 | 池掛在場景物件 | 池內變偽 null；池本身需要跨場景或隨場景重建 |
| 20.6 | 池沒有上限 | 峰值後不縮 | 記憶體高水位（既有「Object Pool Misuse」） |
| 20.7 | 預熱不足導致首次使用 `Instantiate` 卡頓 | 戰鬥中才建立 | 首次技能／特效卡頓 |
| 20.8 | 歸還時只 `SetActive(false)` 不處理 coroutine、事件、動畫 | 狀態殘留 | 重新啟用時舊 coroutine 已被停止（見 1.2.6），舊事件仍訂閱 |

---

## 21. 字串與本地化

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 21.1 | 文化設定依裝置語系 | `ToString()`、`float.Parse`、`string.Format` 預設用目前文化 | 土耳其語 `i`/`I` 大小寫轉換、德法語小數逗號：同一程式在不同語系機器解析失敗或結果不同；應指定 `CultureInfo.InvariantCulture` |
| 21.2 | 字串拼接組句 | 把句子拆成片段再拼 | 不同語言語序不同，無法翻譯；需用帶佔位符的完整句子 |
| 21.3 | 複數、性別、量詞 | 英文 `s` 規則套用所有語言 | 多語系文字不通順；需 ICU／Smart Format 類機制 |
| 21.4 | 翻譯文字長度差異 | 德文、俄文比中文長數倍 | UI 溢出、截斷（見 8.3.4） |
| 21.5 | 字型缺字 | 不同語言字元集 | 方框、空白（見 8.3.1） |
| 21.6 | 從右到左 (RTL) 語言 | 阿拉伯文、希伯來文 | 文字順序、數字方向、排版錯誤，標準 TMP 需額外處理 |
| 21.7 | 語系切換時已存在的 UI | 文字已設定 | 切換語言後部分介面沒更新；需廣播事件並訂閱 |
| 21.8 | 本地化 key 寫在程式碼字串中 | 魔術字串 | 改 key 後缺漏，顯示 key 本身（既有 F11、A-08） |
| 21.9 | 翻譯缺失時沒有 fallback | 新語言未翻完 | 顯示空白或 key |
| 21.10 | 字串比較沒指定 `StringComparison` | 預設文化敏感 | 排序與比較在不同語系結果不同（既有 E09） |
| 21.11 | `ToLower`／`ToUpper` 用於識別（ID、副檔名） | 文化敏感轉換 | 土耳其語 `"TITLE".ToLower()` 得 `"tıtle"`；應 `ToLowerInvariant` |
| 21.12 | 玩家輸入名稱的長度、字元、emoji | `string.Length` 計 UTF-16 單位 | 一個 emoji 算兩個字元；截斷切在代理對中間產生亂碼 |
| 21.13 | 屏蔽詞／敏感詞過濾只在客戶端 | 客戶端可繞過 | 違規內容送出；需伺服器端過濾 |
| 21.14 | Rich Text／TMP 標籤注入 | 玩家文字含標籤 | 見 8.3.3 |
| 21.15 | 字串配置在熱路徑 | 每幀格式化 | GC（見 4.2.5） |
| 21.16 | 全形半形、Unicode 正規化 | 同一字元多種碼點 | 搜尋、比對失敗；ID 重複判斷漏洞 |

---

## 22. Shader／材質（C# 側）

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 22.1 | 讀取 `renderer.material` 會複製出實例 | 每個 Renderer 得到獨立 Material 實例 | 每次存取（首次）產生新 Material；物件銷毀後實例不會自動釋放 → native 記憶體洩漏〔社〕 |
| 22.2 | 讀取 `renderer.materials`（複數）也會複製整組 | 同上 | 同上；且每次 getter 回傳陣列副本 |
| 22.3 | 在 Update 內存取 `.material` | 每幀檢查 | 首次後不再複製，但仍有存取成本；且容易誤以為改的是共用材質 |
| 22.4 | 改 `sharedMaterial` | 修改的是資產本身 | Editor 中永久改動專案資產；Build 中影響所有共用此材質的物件〔社〕 |
| 22.5 | 為每個物件各自 `Instantiate` 材質 | 想要獨立參數 | 破壞 SRP Batcher／合批，draw call 暴增 |
| 22.6 | 應使用 `MaterialPropertyBlock` 卻改材質 | 逐物件變參數 | 材質實例膨脹；PropertyBlock 也會打斷 SRP Batcher（依管線而異），需依管線選擇 |
| 22.7 | `Shader.Find("名稱")` | Shader 若沒被任何材質引用，Build 時被剔除 | Editor 找得到，Build 回 null → 粉紅或 NRE |
| 22.8 | Shader Variant 剝除 | 執行期才啟用的 keyword 在 Build 時未包含 | 材質顯示粉紅或功能缺失；需 Shader Variant Collection 或 `multi_compile` 設定 |
| 22.9 | Shader 首次使用時編譯 | 變體第一次出現才載入／編譯 | 首次出現特效時卡頓；需預熱（Shader Variant Collection WarmUp） |
| 22.10 | 屬性名字串版 `SetFloat("_Intensity")` | 見 4.3.5 | 每次字串→ID；名稱錯誤靜默無效 |
| 22.11 | 屬性名與 Shader 實際宣告不同（`_Color` vs `_BaseColor`） | 不同管線（Built-in／URP）屬性名不同 | 設定無效果 |
| 22.12 | `Material.SetTexture` 傳入 null | 貼圖被釋放或載入失敗 | 顯示預設白貼圖或黑色，難以辨別 |
| 22.13 | 管線切換（Built-in → URP/HDRP）後材質失效 | Shader 不相容 | 全部粉紅；自訂 Shader 需重寫 |
| 22.14 | `Texture.SetPixels` 後忘記 `Apply()` | 修改只在 CPU 端 | 畫面不更新；且 Apply 本身昂貴，需批次呼叫 |
| 22.15 | 執行期建立的 Mesh／Material 沒 `Destroy` | native 資源 | 洩漏（見 7.4.4） |

---

## 23. Debug.Log 與效能

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 23.1 | `Debug.Log` 在 Release Build 仍執行 | Unity 預設不剝除 | 即使不顯示也要格式化字串、擷取堆疊 → 每次呼叫成本高（可達毫秒級，視平台與堆疊設定） |
| 23.2 | Update 內每幀 `Debug.Log` | 圖方便 | 嚴重掉幀、日誌檔暴增、行動端發熱 |
| 23.3 | `Debug.Log` 的字串組裝在呼叫前就做 | `Debug.Log("x=" + x)` | 即使日誌關閉也產生垃圾；應用 `[Conditional]` 包裝讓呼叫點整個被移除 |
| 23.4 | 日誌輸出到螢幕上的調試 UI（IMGUI） | `OnGUI` 每幀多次呼叫 | 嚴重 GC 與 CPU；Release 殘留 |
| 23.5 | 日誌含敏感資料（token、帳號、玩家資料） | 日誌可被匯出 | 資料外洩；日誌檔存在公開路徑 |
| 23.6 | 日誌 IO 同步寫檔 | 每條都 flush | 主執行緒卡頓 |
| 23.7 | 錯誤日誌被當成流程控制 | 例外只 Log 不處理 | 錯誤累積成正常狀態；測試看不出問題（既有 C02、H1） |
| 23.8 | 日誌缺少關鍵上下文（玩家 ID、場景、版本） | 純文字訊息 | 線上問題無法定位（既有 H2、H3） |
| 23.9 | 開發用的 Cheat／GM 指令殘留在 Release | `#if` 沒包 | 玩家可呼叫（見 28） |

---

## 24. 第三方 SDK 整合

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 24.1 | SDK 回呼在非主執行緒 | 原生層回呼（Android JNI、iOS 回呼）來自其他執行緒 | 直接碰 Unity API → 例外或崩潰；需轉送到主執行緒 |
| 24.2 | SDK 多個版本衝突（兩個 SDK 各帶不同版本的同一依賴） | Android Gradle、iOS CocoaPods 依賴衝突 | Build 失敗或執行期 `NoSuchMethodError`；需 External Dependency Manager 解析 |
| 24.3 | SDK 帶的原生函式庫與 Unity 版本不相容 | 舊 SDK + 新 Unity | 載入失敗、崩潰、64 位元／ABI 缺失 |
| 24.4 | SDK 需要的 `link.xml` 保留規則缺失 | 見 13.2.5 | Release 下初始化失敗 |
| 24.5 | SDK 與熱更程式碼互相呼叫 | 熱更程式碼呼叫 SDK 的泛型或委派 | AOT 泛型或適配器問題（見 §14） |
| 24.6 | SDK 的回呼委派被 GC 回收（JNI／P/Invoke） | 委派物件沒被保持參照 | 原生層回呼時崩潰（native 持有的委派被 GC） |
| 24.7 | SDK 回呼觸發時 Unity 物件已銷毀 | 非同步回呼 | MissingReferenceException（見 1.3.6） |
| 24.8 | 廣告 SDK 展示期間 Unity 暫停 | 全螢幕廣告觸發 `OnApplicationPause` | 遊戲邏輯誤認為切後台：重連、存檔、音樂停止；廣告結束後狀態不一致 |
| 24.9 | 廣告／支付回呼可能不回來 | 網路、使用者中斷、App 被殺 | UI 永遠鎖定等待；需逾時與狀態恢復 |
| 24.10 | 內購（IAP）未處理中斷的交易 | 付款後 App 被殺 | 玩家付了錢沒拿到道具；啟動時需處理未完成交易 |
| 24.11 | 內購收據只在客戶端驗證 | 可被偽造 | 刷道具；需伺服器驗證 |
| 24.12 | 內購重複發放 | 回呼重送、重新連線 | 沒有交易 ID 去重 |
| 24.13 | SDK 要求的權限、Manifest、Info.plist 設定缺漏 | Build 時合併不全 | 執行期功能無聲失效或審核被拒 |
| 24.14 | 依賴 SDK 的伺服器端服務停止 | 第三方服務下線／改版 | 啟動時阻塞等待 SDK 回應；沒有逾時就卡死在載入畫面 |

---

## 25. 客戶端網路與同步

> 伺服器端的 Socket／協定／封包問題見 Server 篇 §5、§7；這裡只收「客戶端特有」。

### 25.1 連線與執行緒
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 25.1.1 | 網路收包回呼直接改 UI／GameObject | 回呼在 IO 執行緒 | 例外或畫面不更新（見 3.1.3；既有 G1） |
| 25.1.2 | 在主執行緒做網路收送與解析 | 解析大封包佔用主執行緒 | 卡頓（既有 G2） |
| 25.1.3 | 同步阻塞式 `Connect`／`Receive` | 在主執行緒呼叫 | 畫面凍結直到逾時 |
| 25.1.4 | 沒有心跳／無法偵測半開連線 | 手機切換網路、休眠 | 客戶端以為仍連線，實際已斷（既有 D6） |
| 25.1.5 | Wi-Fi 與行動網路切換 | IP 變化，連線中斷 | 沒有自動重連；TCP 逾時過長（數十秒） |
| 25.1.6 | 重連時所有客戶端同時重試 | 伺服器重啟後 | 重連雪崩（既有 D3）；需隨機退避 |
| 25.1.7 | 重連後狀態未重新同步 | 只重建連線，沒重新請求狀態 | 客戶端畫面與伺服器狀態不一致（既有 D5） |
| 25.1.8 | 斷線期間玩家操作被丟棄或排隊後重放 | 沒有明確策略 | 重連後重複送出操作 → 重複扣款／消耗（既有 D4） |
| 25.1.9 | 登入流程的狀態機未處理所有分支 | 例如重複登入、被踢下線、維護中 | 卡在載入畫面，或進入不一致狀態 |

### 25.2 協定與同步
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 25.2.1 | 客戶端與伺服器協定定義各寫一份 | 手動同步 | 欄位順序、型別、列舉值不一致（既有 B9、A-38） |
| 25.2.2 | 協定沒有版本協商 | 新舊客戶端同時存在 | 舊客戶端解析錯誤封包（既有 B4） |
| 25.2.3 | 列舉值直接上線 | 客戶端重排列舉 | 值對應錯位（既有 B6） |
| 25.2.4 | 封包處理順序假設 | 非同步處理或多連線 | 亂序導致狀態錯誤（既有 C6） |
| 25.2.5 | 客戶端預測沒有和解 | 預測結果與伺服器不同 | 畫面回彈／抖動（既有 C3） |
| 25.2.6 | 客戶端用本機時間算冷卻、Buff 到期 | 時間可被改 | 作弊（既有 C7；見 10.3.1） |
| 25.2.7 | 插值與外推 | 延遲抖動 | 其他玩家抖動、瞬移；緩衝大小難調 |
| 25.2.8 | 請求與回應用單一全域回呼 | 並行請求互相覆蓋 | 回應對到錯誤請求；需請求 ID |
| 25.2.9 | 本地模擬戰鬥結果上傳 | 客戶端權威 | 作弊（既有 A1、A3） |

---

## 26. 音訊、粒子、相機

### 26.1 音訊
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 26.1.1 | 同時兩個 AudioListener | 多場景或多相機 | 警告，音訊行為不確定 |
| 26.1.2 | 沒有 AudioListener | 相機被銷毀或停用 | 完全無聲 |
| 26.1.3 | `AudioSource.Play` 同一來源重複播放 | 同一 Source 被覆蓋 | 前一個聲音被截斷；`PlayOneShot` 才可疊加 |
| 26.1.4 | 在 AudioSource 的物件被銷毀的同一幀播放 | 聲音被截斷 | 音效（如死亡聲、爆炸聲）消失；需獨立播放物件 |
| 26.1.5 | 耳機插拔、藍牙裝置切換 | 音訊輸出裝置變化 | 音訊中斷或失聲，需處理 `AudioSettings.OnAudioConfigurationChanged` |

### 26.2 粒子與特效
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 26.2.1 | 粒子數量上限過高 | `Max Particles` | 行動端 CPU／填充率爆表 |
| 26.2.2 | 粒子重疊 Overdraw | 大面積半透明粒子 | GPU 填充率瓶頸，發熱 |
| 26.2.3 | 粒子系統物件銷毀時特效突然消失 | 物件與粒子同生命週期 | 死亡特效被截斷；需分離或 `Stop` 後延遲銷毀 |
| 26.2.4 | UI 特效（粒子在 Canvas 前面） | 排序層、Canvas 渲染模式 | 粒子被 UI 蓋住或蓋住 UI；需 Sorting Layer 與 UIParticle |

### 26.3 相機
| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 26.3.1 | `Camera.main` 回傳 null | 沒有 MainCamera tag，或相機被停用／銷毀 | NRE；Camera.main 查找成本見 4.2.7 |
| 26.3.2 | Camera 的 Culling Mask 與 Layer 設定 | 同一 Layer 同時決定渲染與碰撞（見 9.4） | 物件不顯示，或改渲染分層時連帶改變碰撞 |
| 26.3.3 | `ScreenToWorldPoint` 缺少深度 | 見 18.8 | 位置錯誤 |
| 26.3.4 | 在 Update 內設相機位置，目標在 FixedUpdate 移動 | 更新階段不同 | 抖動（見 1.4.3） |

---

## 27. Build 與專案設定

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 27.1 | Scripting Define Symbols 在各平台／設定檔不一致 | 手動維護 | 某平台編譯進了不該有的程式碼，或缺少（見 15.4.1） |
| 27.2 | 開發用 Define（`DEBUG_CHEAT`）殘留在 Release 設定 | Build 設定未區分 | Release 含作弊指令（見 28） |
| 27.3 | Development Build 與 Release Build 行為差異 | Safety Checks、Profiler、Stripping、`Debug.Assert` | 見 16.10；只在 Release 出現的 bug |
| 27.4 | Managed Stripping Level 設定高 | 見 13.2.6 | 反射功能失效 |
| 27.5 | Scripting Backend 切換（Mono / IL2CPP） | 泛型、反射、執行緒行為不同 | 見 §13；開發用 Mono、發行用 IL2CPP 導致問題集中在發行階段 |
| 27.6 | API Compatibility Level (.NET Standard vs .NET Framework) | 可用 API 集合不同 | 某些 BCL 類別在目標平台不存在 |
| 27.7 | 多 asmdef 的依賴與循環 | 組件邊界 | 編譯錯誤或被迫放寬；`Auto Referenced` 導致意外耦合 |
| 27.8 | 缺 asmdef 使整個專案是單一組件 | 任一改動全專案重編 | 編譯時間隨規模線性增長，迭代變慢 |
| 27.9 | Plugin 的平台設定 | 勾選平台錯誤 | Editor 能用、Build 缺少原生庫；或 32/64 位元缺失 |
| 27.10 | Android 簽章（Keystore）遺失或密碼錯 | 沒備份 | 無法更新已上架的 App |
| 27.11 | Bundle ID／版本號未遞增 | 手動管理 | 商店拒收、熱更判斷錯誤 |
| 27.12 | 版本號只存在 Player Settings | 程式碼取 `Application.version` | 熱更、協定版本、伺服器檢查依賴它，更新漏了就判斷錯 |
| 27.13 | Build Settings 場景列表缺場景 | 新增場景未加入 | `LoadScene` 找不到（見 6.3.4） |
| 27.14 | Build 流程依賴人手操作 | 沒有 CI | 版本不一致、漏步驟 |
| 27.15 | 套件管理（Package Manager）版本漂移 | `manifest.json` 未鎖定 | 不同開發者拿到不同版本套件 |
| 27.16 | Library 資料夾或 .meta 進版控的策略不當 | 見 6.1.2 | 資源 GUID 漂移 |

---

## 28. 客戶端安全與防作弊

> 伺服器端驗證問題見 Server 篇 §17；語料庫 A1～A5（信任邊界）。這裡只收客戶端側的攻擊面。

| # | 危險狀態 | 觸發原因 | 異常/後果 |
|---|---------|---------|----------|
| 28.1 | Mono（Assembly-CSharp.dll）可被輕易反編譯 | Mono 後端產出 IL | 邏輯、金鑰、協定全部暴露；IL2CPP 提高門檻但 global-metadata 仍可還原結構 |
| 28.2 | IL2CPP 的 `global-metadata.dat` 可被工具還原類別與方法名 | 工具如 Il2CppDumper | 函式名稱與結構外洩，便於掛鉤與修改 |
| 28.3 | 記憶體修改（Cheat Engine、GameGuardian） | 數值明文存在記憶體 | 修改血量、金幣；需混淆敏感數值（只提高門檻），權威在伺服器 |
| 28.4 | 時間加速／修改系統時間 | 見 10.3.1 | 冷卻跳過、離線收益作弊 |
| 28.5 | 封包重放／篡改 | 沒有簽章、序號 | 重送「獲得獎勵」封包（既有 C5） |
| 28.6 | 客戶端上傳結果 | 見 25.2.9 | 刷分、刷道具 |
| 28.7 | 硬編碼密鑰／API Key 在程式碼或資源中 | 打包進 App | 被提取後濫用（既有 Hard-coded Secrets） |
| 28.8 | 加密金鑰與密文放在同一包裡 | 對稱加密金鑰內嵌 | 等於沒加密，只能阻擋非專業者 |
| 28.9 | 存檔／PlayerPrefs 明文 | 見 17.1.2 | 玩家可直接改 |
| 28.10 | 除錯／GM 指令殘留在 Release | 見 23.9、27.2 | 玩家呼叫開發指令 |
| 28.11 | 自訂 URL Scheme／Deep Link 未驗證參數 | 外部可觸發 | 被惡意連結觸發內部功能 |
| 28.12 | WebView 載入外部頁面並暴露原生橋接 | JS 可呼叫 App 功能 | 任意程式碼／資料洩漏 |
| 28.13 | 未驗證熱更/資源的簽章 | 見 14.6.1 | 資源被置換為惡意內容 |
| 28.14 | 憑證綁定（Certificate Pinning）缺失或過度 | 缺失則可中間人；過度則憑證更換時全部連不上 | 安全或可用性損失，需有更新機制 |
| 28.15 | 離線模式下的驗證縮減 | 為了流暢允許離線 | 離線期間作弊無法偵測，回線後需補驗證 |

---

## Part 1 統計摘要

| 分類 | 項目數 | 分類 | 項目數 |
|------|--------|------|--------|
| 1. MonoBehaviour 生命週期與執行順序 | 31 | 15. 平台與行動端 | 21 |
| 2. Update／FixedUpdate／Coroutine／async | 29 | 16. Editor 與 Runtime 混用 | 11 |
| 3. 主執行緒獨占 API 與 Jobs／Burst | 15 | 17. 存檔與本地資料 | 21 |
| 4. Unity GC 與每幀配置 | 19 | 18. 輸入 | 9 |
| 5. Unity 序列化 | 22 | 19. 多場景與場景載入 | 6 |
| 6. Prefab／Scene 參照與遺失 | 13 | 20. 物件池與 Instantiate／Destroy | 8 |
| 7. 資源載入與記憶體 | 34 | 21. 字串與本地化 | 16 |
| 8. UI（UGUI／TMP／UI Toolkit） | 25 | 22. Shader／材質（C# 側） | 15 |
| 9. 動畫與物理 | 22 | 23. Debug.Log 與效能 | 9 |
| 10. 時間與幀率 | 16 | 24. 第三方 SDK 整合 | 14 |
| 11. 浮點、決定性與隨機 | 18 | 25. 客戶端網路與同步 | 18 |
| 12. 事件、委派與單例殘留 | 16 | 26. 音訊、粒子、相機 | 13 |
| 13. IL2CPP／AOT／Code Stripping | 19 | 27. Build 與專案設定 | 16 |
| 14. 熱更系統（ILRuntime／HybridCLR） | 48 | 28. 客戶端安全與防作弊 | 15 |
| **Part 1 小計** | **519 項** | | |

---
---

# Part 2：Unity 壞味道全集（Code Smells）

> 壞味道 ≠ Bug。壞味道是**尚未爆炸的結構性問題**，它們讓程式碼更難理解、更難維護、更容易在未來引發 Part 1 的異常。
> 欄位：**怎麼認**＝可數、可 grep 的特徵；**怎麼修**＝一句話的處方；**既有**＝本機語料庫 `_AIDocs/Research/code-smells/` 已有的條目（已有者不重寫，「怎麼認／怎麼修」以「—」帶過；Unity 引擎層才完整寫）。
> 「既有」欄代號：`03:H12` ＝ `03-csharp-dotnet.md` 條目 H12；`04:G4` ＝ `04-client-server.md` 的〔G4〕；`09:A-17` ＝ `09-local-knowledge.md` 的 A-17；`01/02/05/06/07/08:` 後接英文條名 ＝ 對應分支檔。完整速查見 `00-index.md`。
> 數值門檻（行數、個數）是起點，不是定論，請依自家專案校準。

---

## 29. MonoBehaviour 結構壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 29.1 | **上帝 MonoBehaviour** | 單檔超過約 1000 行；同時出現輸入、移動、戰鬥、UI、網路、存檔相關欄位；Update 內 if/switch 超過 10 個分支 | 依職責切成多個小元件，MonoBehaviour 只當「膠水」，邏輯移到純 C# 類別 | 03:H12、09:A-18 |
| 29.2 | **邏輯全寫在 MonoBehaviour 內（無純 C# 層）** | 專案內可單元測試的非 MonoBehaviour 類別佔比低；任何邏輯都需要場景才能跑 | 抽出純 C# 邏輯類別（可 `new`、可 EditMode 測試），MonoBehaviour 只轉發 | — |
| 29.3 | **Update 輪詢取代事件** | Update 內 `if (state != lastState)` 之類比較；多個物件每幀檢查同一條件 | 改為狀態變更時發事件；或降頻檢查 | 09:A-17、03:H04 |
| 29.4 | **空 Unity 訊息方法** | 搜尋 `void Update()\s*\{\s*\}` 有命中 | 刪除 | 03:H04 |
| 29.5 | **Awake／Start／OnEnable 職責混亂** | 同一類別在三處都做初始化；初始化順序靠註解說明 | 約定：Awake 管自身、Start 管與他人互動、OnEnable/OnDisable 成對訂閱與退訂 | 09:A-16 |
| 29.6 | **Start 內承擔重複初始化需求** | 池化物件的重置邏輯寫在 Start；或 OnEnable 與 Start 做同一件事 | 重置邏輯放 OnEnable 或明確的 `Init()/Reset()` | — |
| 29.7 | **public 欄位當設定與狀態** | 搜尋 `public (int\|float\|bool\|string)` 數量多；Inspector 設定值與執行期狀態混在同一欄位 | 設定用 `[SerializeField] private`，執行期狀態獨立欄位或屬性 | 03:F06 |
| 29.8 | **OnGUI 在正式碼** | 搜尋 `OnGUI` 在非 Editor 資料夾有命中 | 改 UGUI／UI Toolkit，或限定於 `#if DEVELOPMENT_BUILD` | — |
| 29.9 | **MonoBehaviour 建構子／欄位初始化器做事** | 建構子內有 Unity API 呼叫或 `new` 重物件 | 移到 Awake | 03:F12（概念相近） |
| 29.10 | **一個 GameObject 掛十個以上元件且彼此 GetComponent** | Inspector 元件列表很長；元件內互相 `GetComponent<另一個自家元件>()` | 明確合併或用單一協調者；元件間改為介面／事件 | 02:Hub-like Modularization |
| 29.11 | **以 GameObject 當資料容器** | 場景中大量空物件只放設定欄位；用 `FindObjectOfType` 讀設定 | 用 ScriptableObject 或純資料表 | — |
| 29.12 | **MonoBehaviour 內放大量 static 狀態** | 搜尋 `static` 欄位在 MonoBehaviour 類別內 | 移到專屬服務／資料類別，並處理 Domain Reload | 03:F04、09:A-05 |
| 29.13 | **方法名藏副作用** | `GetXxx()` 內 `Instantiate`、改狀態 | 改名或拆成查詢與命令 | 09:A-31、07:Hidden Side Effects / CQS Violation |
| 29.14 | **Update 內重工作** | Update 內 `Find`、`GetComponent`、`Instantiate`、LINQ、字串組裝 | 快取、事件驅動、池化 | 03:H01、H05、09:A-43 |
| 29.15 | **RequireComponent 缺漏** | 程式碼 `GetComponent<X>()` 後不判空直接用，但沒有 `[RequireComponent(typeof(X))]` | 加屬性或改為明確注入 | — |
| 29.16 | **ExecuteAlways 腳本含執行期副作用** | 搜尋 `ExecuteAlways\|ExecuteInEditMode` 有命中且 Update 內改狀態 | 以 `Application.isPlaying` 隔離，或移出 | — |

---

## 30. 參照與依賴壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 30.1 | **Inspector 拖參照當依賴注入（無驗證）** | 一個元件有超過約 8 個 `[SerializeField]` 參照；沒有 `OnValidate` 或啟動檢查；漏拖只有執行時 NRE | 加啟動驗證（缺哪個欄位直接 Log 並指名）；或集中成一份設定 SO | — |
| 30.2 | **Inspector 參照鏈過長** | 為了拿到某物件，需穿過三層以上被拖入的物件 | 提供明確的服務介面，或把依賴直接傳進來 | 01:Message Chains |
| 30.3 | **Manager 單例滿天飛** | 專案中 `XxxManager.Instance` 呼叫點超過數百處；Manager 之間互相呼叫 | 縮減數量、改用建構注入或輕量 Service Locator；Manager 只負責生命週期，不堆業務 | 03:F05、04:G4、09:A-23、02:Singleton Abuse |
| 30.4 | **Find 鏈（Find + Find + GetComponent）** | `GameObject.Find("A").transform.Find("B").GetComponent<C>()` | 序列化參照或註冊式查找（物件啟用時向服務註冊） | 03:H01、01:Message Chains |
| 30.5 | **FindObjectOfType 當全域存取** | 搜尋 `FindObjectOfType\|FindAnyObjectByType` 數量多、出現在 Update／回呼 | 顯式註冊或注入 | 03:H01 |
| 30.6 | **單例 getter 內自動建立** | `Instance` getter 內 `new GameObject` | 禁止隱式建立，找不到就報錯；由啟動流程統一建立 | — |
| 30.7 | **單例初始化順序依賴註解** | 「請確保 A 在 B 之前初始化」的註解 | 啟動流程顯式排序（Bootstrap），或由依賴方等待就緒事件 | 09:A-16 |
| 30.8 | **Service Locator 取代建構注入** | 類別內部呼叫 `ServiceLocator.Get<T>()` 十處以上 | 依賴由外部傳入；Locator 只留在組合根 | 03:F05、02:Service Locator Abuse |
| 30.9 | **靜態類別持有場景物件參照** | `static` 欄位型別是 `GameObject\|Transform\|Component` | 改由場景內的持有者管理，並在銷毀時清除 | 09:A-05 |
| 30.10 | **跨場景靠靜態欄位傳資料** | 場景 A 寫 `GameData.xxx`，場景 B 讀取 | 明確的場景參數物件，載入後清除 | — |
| 30.11 | **GetComponent 後不判空** | `GetComponent<X>().Foo()` 直接鏈式呼叫 | 用 `TryGetComponent` 或 `RequireComponent` | — |
| 30.12 | **Tag／Name 當型別使用** | `if (go.name == "Boss")`、`CompareTag` 取代型別判斷 | 用元件型別或 enum 欄位標識 | 03:H03 |
| 30.13 | **循環依賴的 asmdef／命名空間** | asmdef 被迫互相引用，或用 `Auto Referenced` 繞過 | 重新分層；抽出共用介面組件 | 02:Cyclically-dependent Modularization |
| 30.14 | **玩法層直接依賴 UI 類別** | 戰鬥邏輯類別 `using` UI 命名空間、直接呼叫 `Text.text=` | 玩法層發事件，UI 層訂閱 | 04:G3 |
| 30.15 | **全域 static Action／event 做跨模組溝通** | 搜尋 `public static (event )?Action` | 見 31 | 03:B05 |

---

## 31. 事件與訊息壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 31.1 | **事件匯流排義大利麵** | 事件型別超過約 100 種；發送者與接收者無法靠 IDE 導航；除錯只能搜字串 | 縮小事件範圍（按模組）；以強型別事件；重要流程改直接呼叫 | 04:G5、02:Ambiguous Interface |
| 31.2 | **事件名／事件 ID 用字串或 int 常數** | `Dispatch("OnBattleEnd", …)`、`Event.Send(1005, …)` | 強型別事件類別或泛型事件 | 03:F11 |
| 31.3 | **訂閱無退訂** | 搜尋 `+=` 數量遠大於 `-=` | 成對寫在 OnEnable/OnDisable；或統一用可釋放的訂閱 token | 03:B05、09:A-15、05:Event Subscription Leak |
| 31.4 | **事件載荷是 object／Dictionary** | 接收端大量 `as` 轉型或 `args["key"]` | 強型別載荷 | 04:B6（概念相近） |
| 31.5 | **事件鏈（A 觸發 B 再觸發 A）** | 事件處理函式內再發同類事件 | 加重入保護，或改為排程到下一幀 | — |
| 31.6 | **SendMessage／BroadcastMessage** | 搜尋 `SendMessage\|BroadcastMessage` 有命中 | 改為介面或 C# event | 09:A-39 |
| 31.7 | **UnityEvent 在 Inspector 綁字串方法並承載業務流程** | 大量場景／prefab 內 UnityEvent 綁定關鍵邏輯；程式碼搜不到呼叫者 | UnityEvent 只用於表現層；流程用程式碼 | — |
| 31.8 | **事件發送時順序依賴訂閱順序** | 訂閱者之間有「必須先於某某」的註解 | 明確定義階段（Pre/Post），或改為管線 | — |
| 31.9 | **事件處理函式內拋例外中斷後續訂閱者** | 多播委派直接 `Invoke()` | 逐一呼叫並個別 try/catch，記錄後繼續 | 03:C02（相關） |
| 31.10 | **無法追蹤事件來源** | 看不到誰發了這個事件（沒有來源與關聯 ID） | 開發版事件記錄；事件攜帶來源資訊 | 04:H2 |

---

## 32. 繼承與 Prefab 壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 32.1 | **繼承只為共用 prefab／Inspector 欄位** | 基底類別多數成員是 `[SerializeField]` 欄位而無行為；子類別大量空殼 | 改為組合：多個小元件加共用 prefab variant | 01:Refused Bequest、02:Broken Hierarchy |
| 32.2 | **MonoBehaviour 繼承鏈超過三層** | 類別圖 `A : B : C : D : MonoBehaviour` | 壓平；以組合取代 | 03:F07、02:Deep Hierarchy |
| 32.3 | **Template Method 過度（基底定義 OnXxx 十個虛方法）** | 子類別大多數虛方法空實作或只呼叫 base | 改用策略物件或事件 | 02:Speculative Hierarchy |
| 32.4 | **子類別需要記得呼叫 base.Awake()** | 沒呼叫就壞，且沒有編譯期保護 | Template Method：基底 `sealed Awake` 呼叫 `protected virtual OnAwake` | 03:F12（相近） |
| 32.5 | **Prefab Variant 鏈過深（超過三層）** | Variant of Variant of Variant | 壓平，或把差異資料外移到 SO | — |
| 32.6 | **Prefab 覆寫過量** | 單一實例或 Variant 的 Overrides 清單超過約 20 項 | 該差異應有自己的 Variant 或資料物件 | — |
| 32.7 | **巢狀 Prefab 當作版面組裝工具而非模組** | 一個 prefab 內含十多層巢狀 prefab，改一處需展開多層 | 控制巢狀深度；以功能邊界切 | — |
| 32.8 | **同型 prefab 複製貼上後各自微調** | 多個 prefab 差異只有幾個欄位，但沒有繼承關係 | 用 Variant 或參數化 | 01:Duplicated Code |
| 32.9 | **虛方法在 Awake 時呼叫子類別尚未初始化的欄位** | 基底 Awake 呼叫 virtual | 見 32.4 | 03:F12 |
| 32.10 | **介面只為「抽象」而抽象** | 每個類別都有一個唯一實作的 `IXxx` | 有第二實作需求或測試需求時才抽 | 01:Speculative Generality |
| 32.11 | **用繼承區分資料差異（Sword : Weapon、Axe : Weapon 只差數值）** | 子類別只有建構子賦值 | 資料驅動（SO／表） | 02:Missing Abstraction（反向） |
| 32.12 | **「類型」enum 加大 switch 分派行為** | 多處重複 `switch (type)` | 行為物件／策略 | 01:Repeated Switches |

---

## 33. 流程控制壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 33.1 | **Coroutine 當狀態機** | 單一 coroutine 超過約 100 行；內有多個 `yield return` 夾雜狀態判斷；以區域變數記錄流程狀態 | 明確的狀態機類別（可序列化、可中斷），或 async 加取消 token | 03:H08（部分） |
| 33.2 | **Coroutine 無結束／停止機制** | `while (true)` 內只有 `yield return`，沒有取消條件；沒保存 Coroutine 參考 | 保存參考，在 OnDisable/OnDestroy 停止；或加取消旗標 | 03:H08 |
| 33.3 | **巢狀 Coroutine 長鏈** | 三層以上 `yield return StartCoroutine(...)` | 扁平化；async 搭配 token | 07:Callback Hell / Pyramid of Doom |
| 33.4 | **Invoke／InvokeRepeating 用字串** | 搜尋 `Invoke("` | 改 coroutine 或 `Awaitable`/計時器服務 | 03:F11 |
| 33.5 | **以 bool 旗標組成隱性狀態機** | 欄位中有 `isXxx` 五個以上，且組合有互斥關係 | enum 或明確狀態類別 | 01:Primitive Obsession |
| 33.6 | **fire-and-forget async／Task** | 搜尋 `_ = SomethingAsync()` 或呼叫 async 方法不 await | 加 try/catch 與日誌的包裝，或 UniTask `Forget` 並設全域例外處理 | 03:A07 |
| 33.7 | **async void 非事件處理器** | 搜尋 `async void` | `async Task` 並由呼叫端處理例外 | 03:A01、09:A-14 |
| 33.8 | **等待用 `yield return null` 輪詢條件** | `while (!done) yield return null;` 到處都是 | 以完成事件／Task／callback | 03:G05（相近） |
| 33.9 | **單一方法內以 `Time.time` 手動計時** | 多個 `timer += Time.deltaTime` 欄位 | 統一計時服務 | — |
| 33.10 | **流程腳本散落（誰先誰後只寫在文件）** | 啟動流程分布在多個 Awake／Start | 單一 Bootstrap 場景或啟動管線 | 09:A-16 |
| 33.11 | **深層 if 巢狀處理輸入／UI 狀態** | 巢狀超過四層 | 早返回、狀態物件 | 07:Arrow Code / Deep Nesting |
| 33.12 | **更新順序靠 Script Execution Order 補救** | 專案設定中 SEO 條目超過約 5 個 | 顯式 Tick 管線，由單一更新器按序呼叫 | 09:A-16 |
| 33.13 | **回呼層層傳遞（callback hell）** | `Action<Action<Action>>` 或三層以上的 lambda 巢狀 | async／coroutine 序列化流程 | 07:Callback Hell / Pyramid of Doom |
| 33.14 | **時間相關流程用幀數** | `if (frameCount % 30 == 0)` 的魔數 | 以秒為單位 | 03:F11（魔術數字相近） |

---

## 34. 魔法字串與資料壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 34.1 | **Tag 魔法字串** | 搜尋 `CompareTag("`、`.tag ==` | 常數類別、或用元件型別取代 | 03:H03、F11 |
| 34.2 | **Layer 魔法數字** | `1 << 8`、`gameObject.layer = 9` | `LayerMask.NameToLayer` 結果快取為常數，或序列化 LayerMask | 03:F11 |
| 34.3 | **Animator 參數字串** | `SetBool("isRun"`、`SetTrigger("Attack"` 重複出現 | 靜態類別內的 `Animator.StringToHash` 常數 | 03:H10 |
| 34.4 | **Shader 屬性字串** | `SetFloat("_Xxx"` | `Shader.PropertyToID` 常數 | 03:H10 |
| 34.5 | **場景名／資源路徑字串** | `LoadScene("`、`Resources.Load("Path/`、`Addressables.LoadAssetAsync<>("key"` | 常數表、`AssetReference` 或自動產生的路徑類別 | 03:F11、09:A-35 |
| 34.6 | **PlayerPrefs Key 字串散落** | 搜尋 `PlayerPrefs.(Get\|Set)\w+\("` | 集中定義 Key 與包裝存取器 | 03:F11 |
| 34.7 | **ID 用 int／string 無型別** | 道具 ID、技能 ID、角色 ID 都是 `int`，可互相傳錯 | 強型別 ID 結構 | 01:Primitive Obsession、09:A-22 |
| 34.8 | **設定表欄位以 magic index 存取** | `row[3]`、`cols[7]` | 產生強型別資料類別 | 01:Magic Number |
| 34.9 | **Inspector 裡填的數值有「隱含單位」** | 欄位名叫 `speed`、`time`，不說是秒、度、公尺 | 欄位名帶單位，或用 `[Tooltip]`／`[Range]` | 01:Mysterious Name |
| 34.10 | **用 enum 整數值序列化到存檔／網路** | enum 順序一改就壞 | 明確指定值 `= 10`，並加測試鎖定 | 04:B6 |
| 34.11 | **資料與邏輯混在同一 MonoBehaviour 欄位** | 數值表以 `public` 欄位放在腳本上 | 資料抽 ScriptableObject／表 | 03:F06 |
| 34.12 | **重複的設定來源** | 同一數值同時存在於程式、SO、表 | 單一來源，其餘由工具產生 | 06:Config Sprawl / Multiple Sources of Truth、09:A-08 |
| 34.13 | **日誌／錯誤訊息文字充當程式邏輯鍵** | 以訊息字串做 `Contains` 判斷 | 錯誤碼／強型別錯誤 | 09:A-12 |

---

## 35. UI 架構壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 35.1 | **UI 層含業務規則** | UI 腳本內有價格計算、資格判定、機率 | 規則移到邏輯層，UI 只顯示 | 04:G3、04:A3 |
| 35.2 | **網路回呼直接改 UI** | 封包處理函式內有 `text.text =` | 邏輯層更新資料模型，UI 訂閱 | 04:G1 |
| 35.3 | **每個介面自己管理自己的開關與堆疊** | 到處有 `gameObject.SetActive(false)` 關自己、`UIManager.Close` 混用 | 統一的視窗管理器（堆疊、層級、返回鍵） | — |
| 35.4 | **UI 預製體在 Awake 內 Find 子物件** | `transform.Find("Panel/Btn")` 大量出現 | 序列化參照或自動綁定工具產生欄位 | 03:H01 |
| 35.5 | **按鈕事件用匿名 lambda 註冊且不移除** | `AddListener(() => …)` 在 OnEnable 呼叫 | 成對 Add/Remove，或只註冊一次 | 03:B05 |
| 35.6 | **UI 狀態與資料各存一份** | UI 元件內存 `currentCount` 與模型各一份 | 單向資料流：模型→視圖 | 09:A-02、05:Duplicated State |
| 35.7 | **介面打開時整頁重建（先銷毀再建立）** | 每次開啟 `Instantiate` 全部 item | 池化、虛擬列表、增量更新 | 03:H11 |
| 35.8 | **Canvas 單一巨大** | 整個遊戲 UI 在同一 Canvas，動靜混合 | 靜態與動態分 Canvas | — |
| 35.9 | **Layout Group 巢狀超過三層** | 層級視圖可數 | 手動布局或簡化層級 | — |
| 35.10 | **Raycast Target 全開** | 專案中非互動 Image/Text 的 `raycastTarget` 為 true 的比例高 | 預設關閉，需要時開；用編輯器工具批次檢查 | — |
| 35.11 | **介面之間互相直接引用** | 一個介面類別持有另外三個介面類別的參照 | 經由導航服務／事件 | 04:G4 |
| 35.12 | **動畫與邏輯耦合** | 邏輯依賴動畫事件觸發（Animation Event 做資料變更） | 邏輯與表現分離，動畫只是表現 | — |
| 35.13 | **不同解析度靠硬寫座標** | 程式碼內有像素座標常數 | Anchor、Safe Area、Layout | 01:Magic Number |

---

## 36. 資源與生命週期管理壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 36.1 | **載入與釋放不成對** | 專案內 `LoadAssetAsync` 數量遠大於 `Release` | 資源持有者模式：誰載入誰釋放，集中於 handle 管理類別 | 05:Resource Not Released |
| 36.2 | **各處直接呼叫 Addressables／Resources／AssetBundle API** | 非資源層類別出現 `Addressables.` | 包一層資源服務，統一計數與日誌 | 02:Subsystem-API Bypassed |
| 36.3 | **沒有資源生命週期分組** | 無「場景級／戰鬥級／全域級」概念 | 依生命週期建立 scope，scope 結束時批次釋放 | — |
| 36.4 | **Instantiate／Destroy 滿天飛** | 戰鬥相關程式碼 `Instantiate(` 數量多、沒有池 | 物件池與預熱 | 03:H11、05:Object Pool Misuse |
| 36.5 | **池沒有統一重設協定** | 各種物件的取出後重置寫在各使用處 | 池化介面 `OnSpawn()/OnDespawn()` | 05:Object Pool Misuse |
| 36.6 | **Resources 資料夾濫用** | Resources 資料夾大小占專案資源比例高 | 遷移到 Addressables／AssetBundle | — |
| 36.7 | **靜態快取字典只加不刪** | 搜尋 `static Dictionary` | 加上限／生命週期綁定／弱參照 | 05:Ever-Growing Static Collection |
| 36.8 | **以 `UnloadUnusedAssets`／`GC.Collect` 掩蓋洩漏** | 切場景流程中固定呼叫 | 找洩漏根源 | 03:B09 |
| 36.9 | **material／mesh 實例未銷毀** | 搜尋 `\.material\b` 非 `sharedMaterial` | 持有並在銷毀時 Destroy；或用 PropertyBlock | — |
| 36.10 | **IDisposable／handle 沒有擁有者** | 不知道誰負責 Dispose | 明確所有權（建立者擁有） | 03:B01、B02 |
| 36.11 | **場景切換時手動清單式清理** | 一個長長的 `Clear()` 清單，每新增系統就要加一行 | 各系統訂閱「場景卸載」事件自清；或 scope 機制 | 09:A-06 |
| 36.12 | **DontDestroyOnLoad 濫用** | 搜尋 `DontDestroyOnLoad` 在許多類別 | 只留一個根物件，其餘掛其下 | 03:F05 |
| 36.13 | **載入進度靠猜** | 進度條用假動畫 | 回報真實進度，或分階段加權 | — |
| 36.14 | **同步載入在遊戲流程中** | 搜尋 `WaitForCompletion`、`Resources.Load` 於戰鬥中 | 預載入 | — |

---

## 37. 熱更架構壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 37.1 | **主工程與熱更工程互相繼承（主繼承熱更、熱更繼承主，雙向）** | 主工程出現熱更類別名；熱更類別繼承的主工程基底含大量虛方法需適配器 | 單向依賴：熱更→主工程；跨界只走介面、委派與事件，基底類別保持窄 | — |
| 37.2 | **跨界介面過寬** | 主工程暴露給熱更的 API 超過約 100 個，且持續增加 | 縮成薄薄的「平台層」；變動頻繁的邏輯整個放熱更 | 02:Deficient Encapsulation（相近） |
| 37.3 | **主→熱更→主→熱更來回呼叫** | 一次業務流程的呼叫堆疊跨界超過 2 次 | 流程完整放在同一側，只在入口與出口跨界一次 | — |
| 37.4 | **適配器與委派轉換註冊清單散落且手改** | 註冊程式碼分散在多處；產生碼被手動修改 | 集中註冊、全部由工具產生、不手改 | 09:A-08 |
| 37.5 | **以字串反射找熱更類別** | `Type.GetType("…")`、`Assembly.GetType(name)` 於業務碼 | 型別註冊表（啟動時由熱更端主動註冊） | 03:F11、09:A-39 |
| 37.6 | **熱更端跑重運算** | 尋路、戰鬥結算迴圈、大量物件更新放在熱更 | 重運算放主工程，熱更只下指令 | — |
| 37.7 | **熱更與主工程共享可變 static** | 兩邊都讀寫同一個靜態狀態 | 單一擁有者，另一邊走 API | 03:F04 |
| 37.8 | **熱更版本與主程式版本沒有契約** | 沒有「最低主程式版本」「API 版本」欄位 | 在熱更清單中寫明相容範圍並啟動時檢查 | 04:B4 |
| 37.9 | **泛型值型別實例沒有預先登記** | 熱更中使用 `List<自訂struct>`、`Dictionary<struct, …>` 等 | 以工具掃描並生成預先實例化清單，納入建置 | — |
| 37.10 | **Editor 與真機走不同載入路徑** | `#if UNITY_EDITOR` 直接引用熱更組件 | Editor 也走相同載入流程 | 09:A-47 |
| 37.11 | **熱更啟動前業務碼已執行** | 主工程的 Awake 已經用到熱更才有的邏輯 | 啟動場景只含載入器 | 09:A-16 |
| 37.12 | **熱更內容無回退／無驗證** | 沒有 hash／簽章、沒有失敗回退到上個版本 | 下載驗證加雙槽位 | — |

---

## 38. Editor／工具／Build 壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 38.1 | **條件編譯裡混遊戲邏輯** | `#if UNITY_EDITOR` 區塊內有玩法分支 | 條件編譯只放平台適配與診斷；邏輯走同一路徑 | 09:A-47 |
| 38.2 | **到處散落 `#if` 巢狀** | 同一檔案 `#if` 超過 10 組 | 以介面封裝平台差異，每平台一個實作檔 | 02:Missing Hierarchy |
| 38.3 | **Editor 工具直接改 Runtime 資料不標記 Dirty** | 自訂工具修改資產後沒 `EditorUtility.SetDirty` | 工具共用的存取函式處理 Dirty／Undo | — |
| 38.4 | **手動維護清單（場景、資源、Shader 變體）** | 文字檔或程式碼內手列清單 | 由工具掃描產生 | 09:A-06 |
| 38.5 | **Build 流程只存在某台機器／某人腦中** | 沒有 CI，沒有 Build 腳本 | 腳本化並進版控 | 06:Copy-Pasted Build / CI Scripts |
| 38.6 | **asmdef 缺失或過粗** | 單一 Assembly-CSharp | 依模組切 asmdef，單向依賴 | 02:Insufficient Modularization |
| 38.7 | **Editor 腳本與 Runtime 腳本同檔案** | 同檔內 `#if UNITY_EDITOR` 區塊超過 30 行 | 分檔，Editor 放 Editor 組件 | 03:F01（相近） |
| 38.8 | **自製編輯器擴充繞過 Unity 工作流程** | 自訂儲存、自訂 Prefab 流程 | 優先用 Unity 原生機制 | 02:Golden Hammer |
| 38.9 | **Debug／GM 功能與正式功能同碼路徑且無隔離** | 作弊指令在 Release 可呼叫 | 以編譯符號與簽章雙重隔離 | 06:Environment Branching in Code |
| 38.10 | **Define 符號無集中說明** | 專案內 `#if` 用到的符號超過 10 個且無文件 | 集中列表與用途說明 | 06:Config Sprawl |
| 38.11 | **Library／Temp／產物進版控** | `.gitignore` 缺項 | 補 `.gitignore`；.meta 必須入版控 | — |
| 38.12 | **場景／Prefab 大檔多人同時改** | 合併衝突頻繁 | 拆場景、用 Prefab、鎖定流程 | — |

---

## 39. Unity 效能壞味道

> 通論條目（LINQ、閉包、boxing、字串串接、熱路徑反射）見語料庫 03:D03、E01、E02、E04、E07、H05。以下為 Unity 引擎層。

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 39.1 | **每幀 GetComponent／Find／Camera.main** | Profiler 的 GC Alloc 與 `GameObject.Find` 欄位；程式搜尋 | 啟動時快取 | 03:H01、H02 |
| 39.2 | **重複存取回傳陣列的屬性** | `mesh.vertices[i]` 在迴圈內 | 迴圈外取一次 | 03:H06 |
| 39.3 | **每幀更新不變的 UI 文字** | `text.text = …` 每幀無條件賦值 | 值變化才更新 | 03:H05 |
| 39.4 | **動態與靜態 UI 混在同一 Canvas** | Profiler 顯示 `Canvas.BuildBatch` 每幀出現 | 動態元素獨立子 Canvas〔官〕 | — |
| 39.5 | **物理查詢分配版本** | `RaycastAll`／`OverlapSphere` 非 NonAlloc | 改 NonAlloc 與預配置緩衝 | 03:H06 |
| 39.6 | **Transform 階層過深／過寬** | 單一根物件下子物件數千 | 合併、扁平化、池化 | — |
| 39.7 | **Animator 數量過多且不剔除** | 場景有數百個 Animator，Culling Mode 為 Always Animate | 設 Culling Mode、遠處停用 | — |
| 39.8 | **材質／Shader 多樣但不合批** | Frame Debugger 顯示大量相近 draw call | 共用材質、圖集、GPU Instancing、SRP Batcher | — |
| 39.9 | **過度使用 OnTriggerStay／OnCollisionStay** | 大量物件每個物理步進都回呼 | 改為 Enter/Exit 狀態維護 | — |
| 39.10 | **戰鬥中即時 Instantiate 大型 prefab** | Profiler 尖峰對應 `Instantiate` | 預載入加池 | 03:H11 |
| 39.11 | **Debug.Log 殘留於熱路徑** | 搜尋 `Debug.Log` 在 Update／回呼 | 條件編譯包裝或移除 | 05:Excessive Logging / Logging in Hot Path |
| 39.12 | **過早最佳化（無量測的改動）** | 無 Profiler 數據的「最佳化」提交 | 先量測；確認熱點再改 | 05:Premature Optimization |
| 39.13 | **同步序列化大物件於主執行緒** | 存檔／解析大 JSON 在 Update | 分幀或背景處理 | 05:Unnecessary Processing |
| 39.14 | **記憶體不設預算** | 沒有每場景記憶體上限與監控 | 建立預算與自動化檢查 | — |

---

## 40. 測試與可維護性壞味道

| # | 壞味道 | 怎麼認（可數特徵） | 怎麼修 | 既有 |
|---|--------|------------------|--------|------|
| 40.1 | **沒有 EditMode／PlayMode 測試** | 專案內無 Tests 資料夾 | 先為純 C# 邏輯層補 EditMode 測試 | 09:A-45、06:No Test Suite |
| 40.2 | **PlayMode 測試依賴真實場景與時間** | 測試內 `yield return new WaitForSeconds(2)` | 注入時間來源與假資料 | 06:Sleepy Test |
| 40.3 | **邏輯因綁在 MonoBehaviour 而無法測** | 測試必須建立 GameObject 才能呼叫 | 見 29.2 | 06:Hard-to-Test Code |
| 40.4 | **測試依賴全域單例狀態** | 測試之間互相影響、順序有關 | 單例可重設或可注入 | 06:Interacting Tests |
| 40.5 | **只在 Editor 驗證，沒有真機／Release 驗證** | 沒有 IL2CPP Release 冒煙測試 | CI 加真機或模擬器冒煙流程 | 09:A-46 |
| 40.6 | **預製體／場景沒有自動化驗證** | Missing Script、空參照靠人眼發現 | 建置前掃描：Missing、未指派欄位、重複 GUID | — |
| 40.7 | **無啟動時依賴檢查** | 缺項到使用時才 NRE | 啟動時驗證必要參照與設定，缺失即明確報錯 | 04:H1 |
| 40.8 | **Magic 開關控制行為（Cheat 欄位在 Inspector）** | 場景裡有 `debugMode`、`skipTutorial` 勾選 | 集中於開發設定，Release 不編入 | 06:Feature Toggle Debt |
| 40.9 | **沒有崩潰與錯誤上報** | 線上問題只靠玩家描述 | 接崩潰蒐集，帶版本、場景、裝置資訊 | 05:No Metrics、04:H2 |
| 40.10 | **文件與實作脫節** | 流程圖與實際啟動順序不符 | 以程式碼為準，文件記決策與原因 | 06:Outdated / Misleading Comments |

---
---

## Part 2 統計摘要

| 分類 | 項目數 | 分類 | 項目數 |
|------|--------|------|--------|
| 29. MonoBehaviour 結構壞味道 | 16 | 35. UI 架構壞味道 | 13 |
| 30. 參照與依賴壞味道 | 15 | 36. 資源與生命週期管理壞味道 | 14 |
| 31. 事件與訊息壞味道 | 10 | 37. 熱更架構壞味道 | 12 |
| 32. 繼承與 Prefab 壞味道 | 12 | 38. Editor／工具／Build 壞味道 | 12 |
| 33. 流程控制壞味道 | 14 | 39. Unity 效能壞味道 | 14 |
| 34. 魔法字串與資料壞味道 | 13 | 40. 測試與可維護性壞味道 | 10 |
| **Part 2 小計** | **155 項** | | |

---
---

# 全文件總計

| 部分 | 說明 | 項目數 |
|------|------|--------|
| Part 1 | Unity 客戶端異常危險狀態（§1-§28） | 519 |
| Part 2 | Unity 壞味道（§29-§40；語料庫已有者以「既有」欄指過去） | 155 |
| **合計** | **40 個分類** | **674 項** |

---

## 後續步驟

以此清單為錨點，對照實際 Unity 專案排查：
1. 依風險等級排序：崩潰與資料損壞（§3、§5、§6、§13、§14、§17）> 記憶體洩漏（§7、§12、§22）> 卡頓與耗電（§4、§8、§15）> 邏輯錯誤（§1、§2、§10）> 維護成本（Part 2）。
2. 每一項先用 grep 找特徵（`?.` 作用於 UnityEngine.Object、`+=` 與 `-=` 比例、`Find`、`.material`、`Debug.Log`、`async void`、`Resources.Load`），再用 Profiler／Memory Profiler／Frame Debugger 驗證。
3. 只在 Release（IL2CPP）真機驗證 §13、§14 的條目，Editor 與 Mono 下不會暴露。

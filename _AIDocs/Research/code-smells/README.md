# 何謂壞味道（Code Smells）：閱讀樹根

> 讀者：寫程式或審程式的 LLM，以及人。用途：判斷「這段程式碼算不算壞味道、為什麼、怎麼修、什麼時候其實沒事」。
> 查證日：2026-10-08。九個切面平行上網蒐集，加上本機真實專案案例。共 513 條，每條附來源。
> 本檔是根：先在這裡定位，再進分支檔讀條目全文。只讀本檔也能掌握全貌。

**壞味道的定義**：Fowler 說是「表面看得到的跡象，通常對應系統裡更深的問題」（*a surface indication that usually corresponds to a deeper problem in the system*）。重點是「通常」：味道是值得停下來看的提示，不是定罪。來源：https://martinfowler.com/bliki/CodeSmell.html

---

## 0. 查閱流程（LLM 照這個順序做）

1. **定位**：用第 3 節「症狀路由」或第 2 節「閱讀樹」找到分支檔與節。知道名字就直接搜 [00-index.md](00-index.md)。
2. **比對**：讀該條的「辨識訊號」，拿去對程式碼或量測數據。
3. **排誤報**：讀該條的「何時不算」。命中訊號但符合例外，就不報。
4. **分級**：並行正確性類看程式形狀就能報；效能類要有量測，沒有數據只能報「疑似」。
5. **處置**：找到不是終點。能修就當場修，並證明行為與原本完全相同（第 1 節第 8 條）。
6. **引用**：引用條目時連同它的證據標記一起引用（第 6 節），不要把推論說成事實。

---

## 1. 核心觀念（判斷任何味道之前先記住）

1. **味道是提示，不是判決。** Fowler 自己說有些長函式完全沒問題。來源同上。
2. **數字是代理指標，不是判決。** 各工具的門檻差很多。例如參數上限有 2、7、8、10 好幾種說法；Cognitive Complexity 的預設門檻 15，是 Sonar 從 10 往上調到誤報量可以接受為止的結果。詳見 [07](07-readability-metrics.md) 第 I 節與總表。
3. **數量不是壞味道，切分有沒有責任軸才是。** partial 檔數、方法數、行數只當「值得看一眼」的線索。這是使用者在真實專案確立的原則，見 [09](09-local-knowledge.md) B-01。
4. **審查順序**：先問責任怎麼分，再問同一份狀態有幾個寫入點、有沒有單一出入口，最後才看數字。見 [07](07-readability-metrics.md) 第 0 節。
5. **尺度放大會換名字再出現。** Large Class 放大成 God Component，再放大成 Megaservice；Feature Envy 放大成 Connector Envy，再放大成 Inappropriate Service Intimacy。見 [02](02-design-architecture.md) 1.1 節。
6. **依事故嚴重度排優先序。** 在 client/server 系統裡，會直接造成金錢損失的排最前面：信任用戶端、先查後改不是原子操作、重送時重複扣款。見 [04](04-client-server.md) 開頭的優先序表。
7. **極簡不能砍掉可觀測性。** 錯誤訊號、日誌、資源釋放不可刪，禁止靜默失敗。見 [09](09-local-knowledge.md) B-11。
8. **找到就修，並證明行為相同。** 「值不值得拆」只講一句，主體是改動與證據。等值證明的做法見 [09](09-local-knowledge.md) B-20 到 B-22。
9. **一個構想的完成邏輯拐超過三個彎，就是壞味道。** 這是使用者的審查經驗法則，不是業界標準；主流工具都不直接量跨函式的跳轉次數。見 [07](07-readability-metrics.md)「Long Read Path / Bend Count」與 [09](09-local-knowledge.md) B-04。

---

## 2. 閱讀樹

```
壞味道
├─ 程式碼層（函式、類別）
│   ├─ 01 經典目錄 ............ 膨脹、命名與表達、條件與流程、OO 誤用、變更阻礙、可有可無、耦合、共享狀態
│   └─ 07 可讀性與度量 ........ 控制流負荷、跨函式讀路徑、狀態寫入點散落、名實不符、度量與門檻、偵測工具
├─ 設計與架構層（類別之間、套件、元件、服務）
│   └─ 02 設計與架構 .......... PHAME 四類設計味道、Martin 腐化七徵、SOLID、套件原則、架構味道、經典反模式、微服務
├─ 語言與執行期
│   └─ 03 C# / .NET ............ async、資源與生命週期、例外、集合與 LINQ、配置、語言構件濫用、執行緒、Unity
├─ 系統行為
│   ├─ 04 Client/Server ........ 信任邊界、協定、狀態同步、可靠性、伺服器並行、資料存取、Unity 用戶端、可觀測性
│   └─ 05 並行·效能·資源 ...... 共享狀態、鎖、等待、執行緒；白做的工、成長、I/O 往返、配置、排隊；洩漏；雙存；靜默
├─ 周邊產物
│   └─ 06 測試·資料·設定·註解 . 測試壞味道八類、SQL 與資料表、設定與建置、註解
├─ 產生過程
│   └─ 08 AI 寫碼與演化 ....... 看不到全貌、做太多、遮住問題、變更歷史裡的味道；附寫碼 LLM 自檢清單
└─ 實戰
    └─ 09 本機案例與原則 ...... 使用者在真實專案確認過的 48 條、30 條判斷原則、與經典名稱對照、現有掃描工具
```

| 檔 | 切面 | 條數 | 開頭先讀 |
|---|---|---|---|
| [01-classic-catalog.md](01-classic-catalog.md) | Fowler 第 1／2 版、Refactoring Guru、Mäntylä、Wake、Kerievsky | 38 | §1 分類、§2 各家目錄對照、§4 重構手法中譯 |
| [02-design-architecture.md](02-design-architecture.md) | 設計味道、SOLID、套件度量、架構味道、反模式、微服務 | 77 | §1 分類樹、1.1 與經典味道對應、1.2 DesigniteJava 門檻、H 命名衝突 |
| [03-csharp-dotnet.md](03-csharp-dotnet.md) | C# / .NET 與 Unity | 82 | §0 工具規則圖例、§1 分類、§2 依規則編號反查、§4 未查證一覽 |
| [04-client-server.md](04-client-server.md) | 線上遊戲 client/server 與網路 | 57 | 事故優先序表、條目索引、附錄 1 Azure 對照、附錄 3 grep 線索 |
| [05-concurrency-perf-resource.md](05-concurrency-perf-resource.md) | 並行、效能、記憶體與資源（語言中立） | 60 | 查閱規則、分類架構、附錄 A Smith & Williams 速查、附錄 D 研究數據 |
| [06-test-data-config.md](06-test-data-config.md) | 測試、SQL、設定與建置、註解 | 89 | §0 分類與原始分類對照 |
| [07-readability-metrics.md](07-readability-metrics.md) | 可讀性、認知負荷、度量門檻、工具 | 39 | §0 分類、I 數字不是判決、度量—門檻—出處總表 |
| [08-ai-and-evolution.md](08-ai-and-evolution.md) | LLM 寫碼特有味道、變更歷史味道 | 23 | 一、分類與背景數據；三、機器可擋對照；四、自檢清單 |
| [09-local-knowledge.md](09-local-knowledge.md) | 本機真實專案案例與使用者原則 | 48 | 0 案例出處、B 判斷原則、C 經典對照、D 現有工具 |
| [00-index.md](00-index.md) | 全條目一句話索引 | 513 | 用搜尋，不必通讀 |

---

## 3. 症狀路由：看到什麼，讀哪裡

| 你看到的現象 | 先讀 | 再讀 |
|---|---|---|
| 改一個需求要動很多檔 | 01 Shotgun Surgery、Divergent Change | 02 Rigidity、08 Change Coupling、07 Hotspot Analysis |
| 某個欄位或容器的值說不清是誰、何時改的 | 07 C 節 Scattered State Writes | 09 A-01、A-02、A-07；05 D 節；04 C1 |
| 讀懂一個功能要跳很多層 | 07 B 節（讀路徑、純轉接、Indirection Hell、Yo-yo） | 09 A-26 到 A-29；01 Middle Man、Message Chains |
| 巢狀很深、條件很長 | 07 A 節（Cognitive Complexity、Arrow Code） | 01 C 節；09 A-28 |
| 類別很大，或 partial 切很多片 | 01 Large Class | 02 Insufficient／Multifaceted Modularization；03 F01；09 A-18、A-30、原則 B-01 與 B-08 |
| 出錯了卻沒有任何訊號，事後查不到 | 05 E 節 | 03 C 節；04 H 節；08 C 節；09 A2 節 |
| 卡頓、GC 尖峰、每幀配置 | 03 E 節、H 節 | 04 E7；05 B4 |
| 越跑越慢、資料一多就爆 | 05 B 節（The Ramp、Hidden Quadratic） | 04 F 節 |
| 記憶體只升不降 | 05 C1 | 03 B05、B07；09 A-15 |
| 死結、偶發錯誤、執行緒池飢餓 | 03 A03、G 節 | 05 A 節；04 E 節 |
| 外掛、刷物、重複扣款或重複發獎 | 04 A 節、E9、D4 | 05 Check-Then-Act |
| 斷線重連後狀態錯亂、角色被拉回 | 04 C 節、D 節 | — |
| 協定改版後崩潰，或兩端定義對不上 | 04 B4 到 B6、B9 | 09 A-38、A-46 |
| 封包處理器大量複製貼上 | 04 B7、B8 | 09 A-20 |
| 模組互相依賴、拆不開 | 02 E1、D 節 | 02 Cyclically-dependent Modularization |
| 測試時過時不過，或一重構測試就全壞 | 06 A3、A4 | 08 Test Tampering |
| 資料表或 SQL 的設計 | 06 B 節 | 04 F 節 |
| 設定散在多處、程式裡有 if (isDev) | 06 C 節 | — |
| 註解在重述程式碼或寫版本歷史 | 06 D 節 | 08 Narrative Comments；09 A-33 |
| 同一個檔一修再修 | 08 D 節 | 09 A-48；07 Hotspot Analysis |
| 剛讓 AI 寫完或改完一段碼 | 08 全檔與第四節自檢清單 | 本檔第 5 節 |
| 看到 analyzer 警告編號（CA、S、RCS、VSTHRD、UNT） | 03 §2 依規則反查 | — |
| 需要具體門檻數字 | 07 度量—門檻—出處總表 | 02 1.2 DesigniteJava 門檻；01 [MT] 偵測規則 |

---

## 4. C# client/server 專用閱讀路線

使用者主要寫 C# 遊戲伺服器與 Unity 用戶端。審這類程式碼時照這個順序讀：

1. **先排事故**：[04](04-client-server.md) 開頭的優先序表，先掃信任邊界（A 節）、E9、D4。這三類會直接造成金錢損失。
2. **再看語言陷阱**：[03](03-csharp-dotnet.md) 依序讀 A 非同步、B 資源與生命週期、C 例外、G 執行緒；Unity 用戶端加讀 H。
3. **補並行原理**：[05](05-concurrency-perf-resource.md) A 節講語言中立的原理。附錄 D 的研究數據指出：105 個真實並行 bug 裡有 101 個只牽涉兩條以內的執行緒，所以審查時推演「兩條執行緒、兩個存取點」就能抓到大多數問題。
4. **機器先掃一輪**：[04](04-client-server.md) 附錄 3 是可直接 grep 的程式碼字樣；[03](03-csharp-dotnet.md) §2 是規則編號反查表。很多 CA 規則在 .NET 10 預設沒開，要手動打開才抓得到。
5. **對照真實案例**：[09](09-local-knowledge.md) A 節收了使用者兩個遊戲專案的實例，例如狀態寫入點散落、雙存、樣板地獄、空 catch、async void、事件不退訂。
6. **審查與處置**：按 [09](09-local-knowledge.md) B 節的原則判斷與修整，搭配 [07](07-readability-metrics.md) C 節的狀態所有權量法。

---

## 5. 寫完或改完程式碼的自檢（精選）

完整版在 [08](08-ai-and-evolution.md) 第四節。這裡挑出最常漏的幾條：

1. 新增函式、常數、設定前，搜過專案裡有沒有同功能的東西嗎？
2. 這個改動裡，有沒有任何 catch、fallback、預設值會讓錯誤不留痕跡地消失？
3. 修的是根因還是崩潰點？說得出壞值從哪裡來嗎？
4. 同一個可變欄位現在有幾個寫入點？有沒有單一出入口？
5. 一個構想的完成路徑拐了幾個彎？超過三個就回頭重找最短路徑。
6. 新的抽象、參數、helper，現在就有兩個以上用處嗎？
7. 有沒有改、刪、跳過測試，或把測試的期望值寫進產品碼？
8. 註解講的是「為什麼」，還是「改了什麼」？後者該寫進 commit message。
9. 熱路徑上（每幀、每封包、每個 tick）有沒有新增配置、LINQ、反射或阻塞呼叫？
10. 會被重送的操作是冪等的嗎？用戶端送來的值，伺服器驗證過嗎？

---

## 6. 重疊對照：同一個味道出現在多個分支

各分支從不同尺度或語言切入，所以同一個味道常出現好幾次。下表標出主條目，其他分支只補自己的角度。

| 味道 | 主條目 | 其他角度 |
|---|---|---|
| 散彈式修改 Shotgun Surgery | 01 | 07 C（狀態寫入點）、08 Shotgun Fix（修補版）、02 Scattered Parasitic Functionality（架構層，Garcia 明說兩者不同） |
| 狀態寫入點散落、同一事實多份 | 07 C Scattered State Writes | 09 A-01、A-02（真實案例與量法）；05 Duplicated State；04 C1 Dual Source of Truth；08 Multiple Sources of Truth；01 Global Data、Mutable Data |
| 吞例外、靜默失敗 | 05 E 節（語言中立） | 03 C02（C# 寫法與規則）、04 H1（線上事故）、08 Swallowed Errors（AI 傾向）、09 A-10 到 A-13（案例） |
| Sync-over-Async | 03 A03 | 04 E6（伺服器情境）、05 Interdependent Tasks in a Bounded Pool（原理） |
| 事件訂閱不退訂 | 03 B05 | 05 Event Subscription Leak、09 A-15 |
| N+1、聊天式往返 | 04 B1、B3 | 05 B3 節、04 F6 與 06 B4（ORM） |
| Azure 效能反模式 | 04 附錄 1 | 05 附錄 B（簡表） |
| 巨型類別 | 01 Large Class | 02 Insufficient Modularization（門檻）、God Component；07 God Class 偵測策略；05 Blob（效能視角）；03 F01（partial 藏巨型類別）；09 A-18 |
| 純轉接、委派過頭 | 01 Middle Man | 07 Pass-Through Method、Indirection Hell；09 A-29 |
| 過深巢狀 | 07 Arrow Code | 01 Conditional Complexity；09 A-28（使用者門檻：≤2 不管，3 要審，≥4 必重構） |
| 鎖與並行 | 05 A 節（原理） | 03 G 節（C# 寫法）、04 E 節（伺服器情境） |
| 先查後改 Check-Then-Act | 05 A1 | 04 E9（刷物溫床） |
| 重複程式碼 | 01 Duplicated Code | 02 Duplicate Abstraction；08 Reinvented Helper、Copy-Paste；09 A-08、A-19 |
| 魔術數字 | 01 Magic Number | 06 C1；09 A-35 |
| 註解 | 06 D 節 | 01 Comments、07 E 節、08 Narrative Comments、09 A-33 |
| 測試壞味道 | 06 A 節 | 08 C 節（竄改測試、為測試特判）、09 A-45 |
| 熱點與反覆修改 | 08 D 節 | 07 Hotspot Analysis、09 A-48 |
| Singleton、Service Locator、static 可變狀態 | 02 F 節 | 03 F 節、05 Mutable Static State in Server Code |
| 方法名藏副作用 | 07 C 節 Hidden Side Effects、D 節語言學反模式 | 09 A-31 |

**命名衝突**：「Ambiguous Interface」「Unutilized Abstraction」在不同文獻指不同的東西。引用時要說明依據哪個來源，見 [02](02-design-architecture.md) H 節。

---

## 7. 證據等級與誠實聲明

**蒐集方式**：九個研究 agent 在 2026-10-08 各負責一個切面，實際上網查證，1 到 8 號用網路來源，9 號只讀本機檔案。主 session 負責分類、路由、重疊對照與本檔撰寫。

**主 session 親自逐字核對過的項目**（其餘內容是 agent 查證，主 session 未二次核對）：

- Cognitive Complexity 門檻 15 的由來：Sonar 員工 G. Ann Campbell 在社群的原話。
- testsmells.org 列 19 種測試壞味道。
- Fowler 官方改版說明只說壞味道章「約四分之三改寫」，沒有列增刪清單。
- CA2007 在 .NET 10 預設不啟用；官方說應用程式碼一般應整條關掉，它是給函式庫用的。
- NDepend 確實有「欄位不得從所屬型別階層以外寫入」這條規則；編號 ND1905 是 agent 從規則本體讀到的，主 session 沒能核到編號。

**各分支的證據標記不同**，引用時連標記一起引用：

| 檔 | 標記 |
|---|---|
| 01 | （推論）（未查證） |
| 02 | 〔推論〕、未查證 |
| 03 | 推論、未查證；§4 有總表 |
| 04 | 業界經驗、未查證 |
| 05 | 無標記＝讀過原文；〔摘要〕＝只看過搜尋摘要；〔未查證〕 |
| 06 | 〔部分查證〕、〔未查證〕、（經驗值） |
| 07 | ✅ 一手來源、⚠ 二手或來源矛盾、❓ 未查證 |
| 08 | 【論文】【業界報告】【廠商文件】【經典】【業界觀察，未查證】 |
| 09 | 【試過】【讀碼】【文件】【推論】 |

**拿去做工程決策前要自己再核的**：

- CA 規則的預設啟用狀態，會隨 .NET 版本改變。
- 各工具的門檻數字。sonar 門檻取自 sonar-java 原始碼，C# 版可能不同。
- Unity 相關的推論條目，清單在 [03](03-csharp-dotnet.md) §4。
- Wake 補充的六條味道，只查證了名稱與歸類。

**程式碼片段沒有編譯驗證過。**

**蒐集過程中發現並已更正的錯誤**：

- Oddball Solution 出自 Kerievsky《Refactoring to Patterns》，不是 Wake。
- Karwin 書中「密碼加鹽雜湊」的建議已過時，條目改附 OWASP 目前的建議（首選 Argon2id）。
- NDepend 規則編號在網路摘要裡整體錯位一號；ND1007 的說明寫 0.84，程式實際寫 0.91。
- 使用者原則的口頭版「數字是尺不是判決」沒有逐字出現在來源檔，來源檔的寫法是「數字是代理指標」。

---

## 8. 維護

- 新增條目：照所在分支的條目格式寫。標題用 `### 英文名（中文名）`，第一個欄位寫「- 定義：一句話」，這樣才會被抽進索引。
- [00-index.md](00-index.md) 是從各分支抽出「### 標題＋定義行」產生的。本機案例檔則抽「**A-nn 名稱**」粗體條目，沒有定義行就取「案例」或「指標」欄。改了分支後，照同樣規則重抽。
- 本機案例（09）會隨專案演進過時。引用前先確認案例裡的檔案與數字還成立。
